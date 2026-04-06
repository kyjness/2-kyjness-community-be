pipeline {
    agent any

    environment {
        // 💡 1. 민감한 정보(계정 ID)는 동적으로 조회합니다. (안전함)
        AWS_ACCOUNT_ID = sh(script: 'aws sts get-caller-identity --query Account --output text', returnStdout: true).trim()
        AWS_REGION     = 'ap-northeast-2'

        // 💡 2. 파이프라인 설정값: 여기서 단 한 번만 프로젝트 이름을 정의합니다.
        PROJECT_NAME   = 'puppytalk-v2'

        // 💡 3. 위 변수를 조합해서 모든 리소스 이름을 자동으로 생성합니다.
        ECR_REPOSITORY = "${PROJECT_NAME}-be"
        ECR_REGISTRY   = "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
        ECR_IMAGE      = "${ECR_REGISTRY}/${ECR_REPOSITORY}"

        CLUSTER_NAME   = "${PROJECT_NAME}-cluster"
        SERVICE_NAME   = "${PROJECT_NAME}-be-service"

        IMAGE_TAG      = "${env.BUILD_NUMBER}"
    }

    stages {
        stage('1. Checkout') {
            steps {
                checkout scm
            }
        }

        stage('2. ECR login, Docker build & push') {
            steps {
                sh '''
                    set -eu
                    aws ecr get-login-password --region "${AWS_REGION}" | \\
                        docker login --username AWS --password-stdin "${ECR_REGISTRY}"

                    echo "Docker build (context: $(pwd))"
                    docker build -t "${ECR_IMAGE}:${IMAGE_TAG}" -t "${ECR_IMAGE}:latest" .

                    docker push "${ECR_IMAGE}:${IMAGE_TAG}"
                    docker push "${ECR_IMAGE}:latest"
                '''
            }
        }

        stage('3. ECS deploy') {
            steps {
                sh '''
                    set -eu
                    aws ecs update-service \\
                        --cluster "${CLUSTER_NAME}" \\
                        --service "${SERVICE_NAME}" \\
                        --force-new-deployment \\
                        --region "${AWS_REGION}"
                '''
            }
        }
    }

    post {
        always {
            echo '파이프라인 실행 완료'
            sh 'docker image prune -f || true'
        }
        success {
            echo '✅ 백엔드 배포 성공'
        }
        failure {
            echo '❌ 백엔드 배포 실패. 로그를 확인하세요.'
        }
    }
}