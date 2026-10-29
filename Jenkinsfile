pipeline {
    agent any

    options {
        timestamps()
        disableConcurrentBuilds()
    }

    parameters {
        string(name: 'DOCKERHUB_CREDENTIALS_ID', defaultValue: 'dockerhub-credentials-id', description: 'Jenkins Username/Password credential ID for Docker Hub.')
        booleanParam(name: 'PUSH_IMAGES', defaultValue: false, description: 'Push the verified v1, v2, and v3 images to Docker Hub.')
        booleanParam(name: 'DEPLOY_TO_KUBERNETES', defaultValue: false, description: 'Apply manifests and wait for all three deployments.')
    }

    environment {
        DOCKER_REPOSITORY = 'sanguptha/invoice-system'
        KUBECONFIG = 'C:\\Users\\sanph\\.kube\\config'
    }

    stages {
        stage('Checkout source') {
            steps { checkout scm }
        }

        stage('Verify Windows agent') {
            steps {
                bat '''@echo off
                    where docker || exit /b 1
                    docker version || exit /b 1
                    where kubectl || exit /b 1
                    kubectl version --client || exit /b 1
                    if not exist "%KUBECONFIG%" (
                      echo ERROR: KUBECONFIG was not found at %KUBECONFIG%
                      exit /b 1
                    )
                    kubectl config current-context || exit /b 1
                '''
            }
        }

        stage('Run application tests') {
            steps { bat 'docker build --target test --tag invoice-system:test .' }
        }

        stage('Build versioned Docker images') {
            steps {
                bat '''@echo off
                    for %%V in (v1 v2 v3) do (
                      docker build --build-arg APP_VERSION=%%V --tag %DOCKER_REPOSITORY%:%%V . || exit /b 1
                    )
                    docker image inspect %DOCKER_REPOSITORY%:v1 %DOCKER_REPOSITORY%:v2 %DOCKER_REPOSITORY%:v3 || exit /b 1
                '''
            }
        }

        stage('Smoke-test all containers') {
            steps {
                bat '''@echo off
                    call :smoke v1 18081 1 || exit /b 1
                    call :smoke v2 18082 2 || exit /b 1
                    call :smoke v3 18083 3 || exit /b 1
                    goto :eof

                    :smoke
                    docker rm -f invoice-smoke-%1 >nul 2>&1
                    docker run -d --rm --name invoice-smoke-%1 -p %2:8080 %DOCKER_REPOSITORY%:%1 || exit /b 1
                    powershell -NoProfile -NonInteractive -Command "$ErrorActionPreference = 'Stop'; for ($i = 0; $i -lt 20; $i++) { try { $page = (Invoke-WebRequest -UseBasicParsing http://127.0.0.1:%2/).Content; if ($page -match 'Version %3') { exit 0 } } catch {}; Start-Sleep -Seconds 1 }; throw 'Invoice %1 did not become ready.'" || exit /b 1
                    docker rm -f invoice-smoke-%1 || exit /b 1
                    exit /b 0
                '''
            }
        }

        stage('Push verified images to Docker Hub') {
            when { expression { return params.PUSH_IMAGES } }
            steps {
                withCredentials([usernamePassword(credentialsId: "${params.DOCKERHUB_CREDENTIALS_ID}", usernameVariable: 'DOCKERHUB_USER', passwordVariable: 'DOCKERHUB_TOKEN')]) {
                    bat '''@echo off
                        echo %DOCKERHUB_TOKEN% | docker login -u "%DOCKERHUB_USER%" --password-stdin || exit /b 1
                        for %%V in (v1 v2 v3) do docker push %DOCKER_REPOSITORY%:%%V || exit /b 1
                    '''
                }
            }
        }

        stage('Deploy all versions to Kubernetes') {
            when { expression { return params.DEPLOY_TO_KUBERNETES } }
            steps {
                bat '''@echo off
                    for %%V in (v1 v2 v3) do kubectl apply -f k8s\invoice-%%V.yaml || exit /b 1
                    for %%V in (v1 v2 v3) do kubectl rollout status deployment/invoice-%%V --timeout=180s || exit /b 1
                    kubectl get deployments,pods,services -l app=invoice-system -o wide || exit /b 1
                '''
            }
        }
    }

    post {
        always {
            bat '''@echo off
                for %%V in (v1 v2 v3) do docker rm -f invoice-smoke-%%V >nul 2>&1
            '''
        }
        success { echo 'Invoice System pipeline completed successfully.' }
    }
}
