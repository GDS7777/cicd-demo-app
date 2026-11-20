pipeline {
    agent any

    parameters {
        string(name: 'REPO_URL', defaultValue: 'https://github.com/GDS7777/cicd-demo-app.git', description: 'HTTPS URL of the fork to build')
        string(name: 'GIT_BRANCH', defaultValue: 'master', description: 'Existing branch to build')
        booleanParam(name: 'RUN_TESTS', defaultValue: true, description: 'Run unit tests')
    }

    stages {
        stage('Checkout') {
            steps {
                deleteDir()
                script {
                    env.SELECTED_BRANCH = params.GIT_BRANCH
                }
                git branch: params.GIT_BRANCH, url: params.REPO_URL
                script {
                    env.CHECKOUT_SHA = sh(script: 'git rev-parse HEAD', returnStdout: true).trim()
                    echo "Branch: ${params.GIT_BRANCH}"
                    echo "Commit SHA: ${env.CHECKOUT_SHA}"
                }
            }
        }

        stage('Validate') {
            steps {
                sh '''
                    set -eu
                    for item in README.md requirements.txt src tests; do
                        if [ ! -e "$item" ]; then
                            echo "Required project item is missing: $item"
                            exit 1
                        fi
                    done
                    echo "Project structure is valid."
                '''
            }
        }

        stage('Test') {
            when {
                expression { params.RUN_TESTS }
            }
            steps {
                sh 'python3 -m unittest discover -s tests -v'
            }
        }

        stage('Build') {
            steps {
                sh '''
                    set -eu
                    printf 'Build number: %s\\nCommit SHA: %s\\nBranch: %s\\n' "$BUILD_NUMBER" "$CHECKOUT_SHA" "$SELECTED_BRANCH" > build-info.txt
                    tar -czf app.tar.gz --exclude=.git README.md requirements.txt src tests Jenkinsfile build-info.txt
                    tar -tzf app.tar.gz
                '''
            }
        }

        stage('Archive') {
            steps {
                archiveArtifacts artifacts: 'app.tar.gz', fingerprint: true
            }
        }
    }

    post {
        success {
            echo 'Pipeline completed successfully.'
        }
        failure {
            echo 'Pipeline failed. Check the stage and Console Output.'
        }
    }
}

