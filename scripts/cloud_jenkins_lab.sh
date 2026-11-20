#!/usr/bin/env bash
set -euo pipefail

ROOT="$(pwd)"
EVIDENCE="$ROOT/evidence"
JENKINS_HOME_HOST="$RUNNER_TEMP/jenkins-home"
INIT_DIR="$RUNNER_TEMP/jenkins-init"
mkdir -p "$EVIDENCE/screenshots" "$INIT_DIR" "$JENKINS_HOME_HOST"

cat > "$RUNNER_TEMP/Dockerfile.jenkins" <<'DOCKERFILE'
FROM jenkins/jenkins:lts-jdk21
RUN jenkins-plugin-cli --plugins "git workflow-aggregator pipeline-stage-view"
DOCKERFILE

docker build -f "$RUNNER_TEMP/Dockerfile.jenkins" -t jenkins-lab-cloud "$RUNNER_TEMP"
docker image inspect jenkins-lab-cloud --format '{{index .RepoDigests 0}}' > "$EVIDENCE/jenkins-image-digest.txt"

cat > "$INIT_DIR/seed.groovy" <<'GROOVY'
import jenkins.model.Jenkins
import hudson.security.AuthorizationStrategy
import hudson.security.SecurityRealm
import hudson.model.ParametersDefinitionProperty
import hudson.model.StringParameterDefinition
import hudson.model.BooleanParameterDefinition
import org.jenkinsci.plugins.workflow.job.WorkflowJob
import org.jenkinsci.plugins.workflow.cps.CpsFlowDefinition

def instance = Jenkins.get()
instance.setNumExecutors(3)
instance.setSecurityRealm(SecurityRealm.NO_AUTHENTICATION)
instance.setAuthorizationStrategy(AuthorizationStrategy.UNSECURED)
def existing = instance.getItem('JenkinsLab')
def job = existing == null ? instance.createProject(WorkflowJob, 'JenkinsLab') : existing
def script = new File('/tmp/Jenkinsfile').getText('UTF-8')
job.setDefinition(new CpsFlowDefinition(script, true))
job.removeProperty(ParametersDefinitionProperty)
job.addProperty(new ParametersDefinitionProperty([
    new StringParameterDefinition('REPO_URL', 'https://github.com/GDS7777/cicd-demo-app.git', 'HTTPS URL of the fork'),
    new StringParameterDefinition('GIT_BRANCH', 'master', 'Existing branch to build'),
    new BooleanParameterDefinition('RUN_TESTS', true, 'Run unit tests')
]))
job.save()
instance.save()
GROOVY

docker run -d --rm --name jenkins-lab-cloud \
  -p 127.0.0.1:8080:8080 \
  -e JAVA_OPTS="-Djenkins.install.runSetupWizard=false" \
  -v "$INIT_DIR:/usr/share/jenkins/ref/init.groovy.d:ro" \
  -v "$JENKINS_HOME_HOST:/var/jenkins_home" \
  -v "$ROOT/Jenkinsfile:/tmp/Jenkinsfile:ro" \
  jenkins-lab-cloud

JENKINS_URL="http://127.0.0.1:8080"
READY=0
for attempt in $(seq 1 90); do
  if curl -fsS "$JENKINS_URL/login" >/dev/null; then READY=1; break; fi
  sleep 4
done
if [ "$READY" -ne 1 ]; then
  docker logs jenkins-lab-cloud
  exit 1
fi
sleep 5
curl -fsS "$JENKINS_URL/job/JenkinsLab/api/json?tree=name,buildable,property[parameterDefinitions[name,type,defaultParameterValue[value]]]" \
  > "$EVIDENCE/job-configuration.json"

run_build() {
  EXPECTED_BRANCH="$1"
  EXPECTED_TESTS="$2"
  EXPECTED_RESULT="$3"
  PREVIOUS="$4"
  curl -fsS -X POST "$JENKINS_URL/job/JenkinsLab/buildWithParameters?REPO_URL=https%3A%2F%2Fgithub.com%2FGDS7777%2Fcicd-demo-app.git&GIT_BRANCH=$EXPECTED_BRANCH&RUN_TESTS=$EXPECTED_TESTS"
  BUILD_NUMBER=""
  for attempt in $(seq 1 90); do
    BUILD_NUMBER="$(curl -fsS "$JENKINS_URL/job/JenkinsLab/api/json?tree=lastBuild[number]" | jq -r '.lastBuild.number // empty')"
    if [ -n "$BUILD_NUMBER" ] && [ "$BUILD_NUMBER" -gt "$PREVIOUS" ]; then break; fi
    sleep 2
  done
  if [ -z "$BUILD_NUMBER" ] || [ "$BUILD_NUMBER" -le "$PREVIOUS" ]; then
    echo "Timed out waiting for Jenkins build after $PREVIOUS"
    exit 1
  fi
  for attempt in $(seq 1 180); do
    STATE="$(curl -fsS "$JENKINS_URL/job/JenkinsLab/$BUILD_NUMBER/api/json?tree=building,result")"
    BUILDING="$(printf '%s' "$STATE" | jq -r '.building')"
    [ "$BUILDING" = "false" ] && break
    sleep 3
  done
  RESULT="$(curl -fsS "$JENKINS_URL/job/JenkinsLab/$BUILD_NUMBER/api/json?tree=result" | jq -r '.result')"
  printf '%s\n' "$STATE" > "$EVIDENCE/build-$BUILD_NUMBER-status.json"
  curl -fsS "$JENKINS_URL/job/JenkinsLab/$BUILD_NUMBER/consoleText" > "$EVIDENCE/build-$BUILD_NUMBER-console.txt"
  printf 'build=%s branch=%s tests=%s result=%s\n' "$BUILD_NUMBER" "$EXPECTED_BRANCH" "$EXPECTED_TESTS" "$RESULT" | tee -a "$EVIDENCE/build-matrix.txt"
  if [ "$RESULT" != "$EXPECTED_RESULT" ]; then
    echo "Expected $EXPECTED_RESULT but received $RESULT for build $BUILD_NUMBER"
    exit 1
  fi
  if [ "$RESULT" = "SUCCESS" ]; then
    curl -fsS "$JENKINS_URL/job/JenkinsLab/$BUILD_NUMBER/artifact/app.tar.gz" -o "$EVIDENCE/app-$BUILD_NUMBER.tar.gz"
  fi
  echo "$BUILD_NUMBER"
}

B1="$(run_build master true SUCCESS 0)"
B2="$(run_build master false SUCCESS "$B1")"
B3="$(run_build broken-tests true FAILURE "$B2")"
B4="$(run_build master true SUCCESS "$B3")"

grep -Eqi 'skipped.*Test|Test.*skipped|when conditional' "$EVIDENCE/build-$B2-console.txt"
grep -Eqi 'FAILED|failures=1|was not equal' "$EVIDENCE/build-$B3-console.txt"
grep -Eqi 'Stage "Build" skipped|Stage "Archive" skipped' "$EVIDENCE/build-$B3-console.txt"
grep -q 'Pipeline completed successfully.' "$EVIDENCE/build-$B4-console.txt"
tar -xOf "$EVIDENCE/app-$B4.tar.gz" build-info.txt > "$EVIDENCE/build-info.txt"
tar -tzf "$EVIDENCE/app-$B4.tar.gz" > "$EVIDENCE/archive-contents.txt"

printf 'B1=%s\nB2=%s\nB3=%s\nB4=%s\n' "$B1" "$B2" "$B3" "$B4" > "$EVIDENCE/build-numbers.env"
printf 'Jenkins URL: %s\nDocker image digest: %s\n' "$JENKINS_URL" "$(cat "$EVIDENCE/jenkins-image-digest.txt")" > "$EVIDENCE/environment.txt"

npm install --no-save playwright
npx playwright install --with-deps chromium
cat > "$RUNNER_TEMP/capture-jenkins.mjs" <<'NODE'
import { chromium } from 'playwright';
import fs from 'node:fs';
const base = 'http://127.0.0.1:8080';
const out = process.cwd() + '/evidence/screenshots';
const numbers = fs.readFileSync(process.cwd() + '/evidence/build-numbers.env', 'utf8')
  .match(/B[1-4]=(\d+)/g).map(x => x.split('=')[1]);
const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 1 });
await page.goto(base + '/job/JenkinsLab/', { waitUntil: 'domcontentloaded' });
await page.waitForTimeout(2500);
await page.screenshot({ path: out + '/jenkins-stage-history.png' });
for (let i = 0; i < numbers.length; i++) {
  const n = numbers[i];
  await page.goto(base + '/job/JenkinsLab/' + n + '/console', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(500);
  await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
  await page.screenshot({ path: out + '/build-' + n + '-console.png' });
}
await page.goto(base + '/job/JenkinsLab/' + numbers[3] + '/artifact/', { waitUntil: 'domcontentloaded' });
await page.waitForTimeout(500);
await page.screenshot({ path: out + '/build-' + numbers[3] + '-artifacts.png' });
await browser.close();
NODE
node "$RUNNER_TEMP/capture-jenkins.mjs"

docker logs jenkins-lab-cloud > "$EVIDENCE/jenkins-startup.log" 2>&1
docker stop jenkins-lab-cloud
