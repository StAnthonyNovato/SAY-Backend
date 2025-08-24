// Copyright (c) 2025 Damien Boisvert (AlphaGameDeveloper)
// 
// This software is released under the MIT License.
// https://opensource.org/licenses/MIT

pipeline {
    agent {
        docker {
            image 'boisvert/python-build'
            args '-u root --entrypoint=""'
        }
    }

    environment {
        DOCKER_HUB_TOKEN = credentials('alphagamedev-docker-token')
    }
    
    stages {
        stage('Get Version') {
            steps {
                script {
                    // use setuptools-scm
                    sh "pip install setuptools-scm"
                    def version = sh(script: "python3 -c 'import setuptools_scm; print(setuptools_scm.get_version())'", returnStdout: true).trim()
                    env.VERSION = version
                }
            }
        }
        stage("Build Container") {
            steps {
                script {
                    sh "docker build -t alphagamedev/say-backend:${env.VERSION} ."
                }
            }
        }
        stage("Push to Docker Hub") {
            steps {
                script {
                    sh "echo ${DOCKER_HUB_TOKEN} | docker login -u alphagamedev --password-stdin"
                    sh "docker tag alphagamedev/say-backend:${env.VERSION} alphagamedev/say-backend:latest"
                    sh "docker push alphagamedev/say-backend:${env.VERSION}"
                    sh "docker push alphagamedev/say-backend:latest"
                }
            }
        }

        stage("Regenerate Compose on Server and Deploy") {
            steps {
                sshagent(['stanthonyyouth2']) {
                    sh "ssh damien@10.0.0.65 'cd /home/damien/stanthonyyouth/ && ./generateCompose.py ${env.VERSION} && docker compose up -d'"
                }
            }
        }
    }
    post {
        success {
            sh 'curl -X POST -H "Content-Type: application/json" -d \'{"content": "Deployment completed successfully!"}\' https://discord.com/api/webhooks/1399052802872971305/rErIzvXkdDDwNQbAqFm8y08do6c4bZwwud1oJr2t4KUQvE7juaklVg0n2xezuPunMv_1'
            echo 'Deployment completed successfully!'
        }
        failure {
            sh 'curl -X POST -H "Content-Type: application/json" -d \'{"content": "Deployment failed!"}\' https://discord.com/api/webhooks/1399052802872971305/rErIzvXkdDDwNQbAqFm8y08do6c4bZwwud1oJr2t4KUQvE7juaklVg0n2xezuPunMv_1'
            echo 'Deployment failed!'
        }
        cleanup {
            cleanWs()
        }
    }
}

