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
        HOSTS = "10.0.0.167,10.0.0.168" // Comma-separated list of hosts
        REMOTE_USER = 'say'
        REMOTE_PATH = '/opt/stanthonyyouth'
        VENV_DIR = "${REMOTE_PATH}/venv"
    }
    
    stages {
        stage("Stop Service") {
            steps {
                script {
                    def hosts = env.HOSTS.split(',')
                    def tasks = [:]
                    for (host in hosts) {
                        def thisHost = host
                        tasks[thisHost] = {
                            def currentHost = thisHost
                            sshagent(['stanthonyyouth-server']) {
                                sh """
                                    mkdir -p ~/.ssh
                                    chmod 700 ~/.ssh
                                    ssh-keyscan -H ${currentHost} >> ~/.ssh/known_hosts
                                    ssh ${env.REMOTE_USER}@${currentHost} " \
                                        sudo /bin/systemctl stop say-backend.service
                                        rm -rf ${env.REMOTE_PATH}/* ${env.REMOTE_PATH}/.[!.]* ${env.REMOTE_PATH}/..?*  # Clear the remote directory, including hidden files
                                    "
                                """
                            }
                        }
                    }
                    parallel tasks
                }
            }
        }
        stage('Sync Files') {
            steps {
                script {
                    def hosts = env.HOSTS.split(',')
                    def tasks = [:]
                    for (host in hosts) {
                        def thisHost = host
                        tasks[thisHost] = {
                            def currentHost = thisHost
                            sshagent(['stanthonyyouth-server']) { 
                                sh """
                                    ssh-keyscan -H ${currentHost} >> ~/.ssh/known_hosts
                                    python3 -m pip install setuptools-scm
                                    python3 -c "import setuptools_scm; print(setuptools_scm.get_version())" > version.txt
                                    rsync -avz --delete \
                                        --exclude='.git' \
                                        --exclude='Jenkinsfile' \
                                        --exclude='*.log' \
                                        --exclude='*venv*' \
                                        --exclude='*.pyc' \
                                        ./ ${env.REMOTE_USER}@${currentHost}:${env.REMOTE_PATH}/
                                """
                            }
                        }
                    }
                    parallel tasks
                }
            }
        }
        stage('Download Dependencies') {
            steps {
                script {
                    def hosts = env.HOSTS.split(',')
                    def tasks = [:]
                    for (host in hosts) {
                        def thisHost = host
                        tasks[thisHost] = {
                            def currentHost = thisHost
                            sshagent(['stanthonyyouth-server']) { 
                                sh """
                                    ssh ${env.REMOTE_USER}@${currentHost} " \
                                        cd ${env.REMOTE_PATH} && \
                                        python3 -m venv ${env.VENV_DIR} && \
                                        ${env.VENV_DIR}/bin/python -m pip install -r requirements.txt
                                    "
                                """
                            }
                        }
                    }
                    parallel tasks
                }
            }
        }
        stage('Restart Service') {
            steps {
                script {
                    def hosts = env.HOSTS.split(',')
                    def tasks = [:]
                    for (host in hosts) {
                        def thisHost = host
                        tasks[thisHost] = {
                            def currentHost = thisHost
                            sshagent(['stanthonyyouth-server']) { 
                                sh """
                                    ssh-keyscan -H ${currentHost} >> ~/.ssh/known_hosts
                                    ssh ${env.REMOTE_USER}@${currentHost} " \
                                        sudo /bin/systemctl restart say-backend.service
                                    "
                                """
                            }
                        }
                    }
                    parallel tasks
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

