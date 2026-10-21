pipeline {
    agent any
    
    environment {
        // !!! CHANGE THIS to your actual DockerHub username !!!
        DOCKER_USER = 'yourdockerhubusername' 
        IMAGE_NAME  = 'invoice-system'
        TAG         = 'v1'
        CRED_ID     = 'dockerhub-credentials-id' 
    }
    
    stages {
        stage('Checkout Source') {
            steps {
                checkout scm
            }
        }
        
        stage('Build Docker Image') {
            steps {
                sh "docker build -t ${DOCKER_USER}/${IMAGE_NAME}:${TAG} ."
            }
        }
        
        stage('Push to DockerHub') {
            steps {
                withCredentials([usernamePassword(credentialsId: "${CRED_ID}", passwordVariable: 'PASS', usernameVariable: 'USER')]) {
                    sh "echo \$PASS | docker login -u \$USER --password-stdin"
                    sh "docker push ${DOCKER_USER}/${IMAGE_NAME}:${TAG}"
                }
            }
        }
        
        stage('Deploy to Kubernetes') {
            steps {
                sh "kubectl apply -f k8s/invoice-v1.yaml"
            }
        }
    }
}
