
pipeline {
    agent any

    environment {
        // Replace with your actual Docker Hub username
        DOCKER_USER = 'yourdockerhubusername'
        IMAGE_NAME  = 'invoice-system'
        TAG         = 'v1'

        // Jenkins > Manage Jenkins > Credentials
        CRED_ID     = 'dockerhub-credentials-id'

        // Full path to Docker CLI on your computer
        DOCKER_EXE  = 'C:\\Users\\sanph\\AppData\\Local\\Programs\\DockerDesktop\\resources\\bin\\docker.exe'
    }

    stages {
        stage('Checkout Source') {
            steps {
                checkout scm
            }
        }

        stage('Verify Docker') {
            steps {
                bat '"%DOCKER_EXE%" --version'
            }
        }

        stage('Build Docker Image') {
            steps {
                bat '"%DOCKER_EXE%" build -t %DOCKER_USER%/%IMAGE_NAME%:%TAG% .'
            }
        }

        stage('Push to DockerHub') {
            steps {
                withCredentials([
                    usernamePassword(
                        credentialsId: "${CRED_ID}",
                        usernameVariable: 'DH_USER',
                        passwordVariable: 'DH_PASS'
                    )
                ]) {
                    bat '''
                        @echo off
                        echo %DH_PASS% | "%DOCKER_EXE%" login -u "%DH_USER%" --password-stdin
                        if errorlevel 1 exit /b 1

                        "%DOCKER_EXE%" push %DOCKER_USER%/%IMAGE_NAME%:%TAG%
                        if errorlevel 1 exit /b 1
                    '''
                }
            }
        }

        stage('Deploy to Kubernetes') {
            steps {
                bat 'kubectl apply -f k8s/invoice-v1.yaml'
            }
        }
    }

    post {
        success {
            echo 'Invoice v1 pipeline completed successfully!'
        }
        failure {
            echo 'Pipeline failed. Check the Console Output for the failing stage.'
        }
    }
}


