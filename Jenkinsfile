pipeline {
    agent any

    /*
     * Terraform 정합 (ecs.tf, ecr.tf):
     *   - ECR 저장소 이름 : "${var.project_name}-be"
     *   - ECS 클러스터   : "${var.project_name}-cluster"
     *   - ECS 서비스     : "${var.project_name}-be-service"
     *   - 태스크 정의    : 이미지 = "${ecr.repository_url}:latest"
     *
     * Jenkins Job은 이 저장소(백엔드) 루트를 체크아웃해야 함 → docker build 컨텍스트 = .
     * 모노레포 루트에서 빌드한다면 dir('2-kyjness-community-be') { ... } 로 감쌀 것.
     * AWS 인증: Jenkins EC2 IAM Instance Profile (AK/SK·withCredentials 불필요).
     */
    environment {
        AWS_REGION         = 'ap-northeast-2'
        AWS_DEFAULT_REGION = 'ap-northeast-2'

        // 신규 계정/프로젝트 시 수정: AWS 콘솔 → ECR → URI에서 계정 ID 확인
        AWS_ACCOUNT_ID     = '654081961169'

        // Terraform var.project_name 이 "puppytalk" 이면 저장소 이름은 puppytalk-be
        // project_name 을 "puppytalk-v2" 로 쓰면 여기는 puppytalk-v2-be 로 맞출 것
        ECR_REPOSITORY     = 'puppytalk-be'

        ECR_REGISTRY       = "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
        ECR_IMAGE          = "${ECR_REGISTRY}/${ECR_REPOSITORY}"

        CLUSTER_NAME       = 'puppytalk-cluster'
        SERVICE_NAME       = 'puppytalk-be-service'

        IMAGE_TAG          = "${env.BUILD_NUMBER}"
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
                    # docker login 은 레지스트리 호스트만 (리포지토리 경로 포함 시 실패할 수 있음)
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
                    aws ecs update-service \
                        --cluster "${CLUSTER_NAME}" \
                        --service "${SERVICE_NAME}" \
                        --force-new-deployment \
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
