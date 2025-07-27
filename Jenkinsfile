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
        REMOTE_HOST = '10.0.0.167'
        REMOTE_USER = 'say' // Change this to your remote username
        REMOTE_PATH = '/opt/stanthonyyouth' // Change this to your target path
        VENV_DIR = "${REMOTE_PATH}/venv" // Directory for the virtual environment
    }
    
    stages {
        stage("Stop Service") {
            steps {
                sshagent(['stanthonyyouth-server']) {
                    sh '''
                        # Add remote host to known_hosts
                        ssh-keyscan -H ${REMOTE_HOST} >> ~/.ssh/known_hosts

                        ssh ${REMOTE_USER}@${REMOTE_HOST} " \
                            sudo /bin/systemctl stop say-backend.service
                        "
                    '''
                }
            }
        }
        stage('Sync Files') {
            steps {
                sshagent(['stanthonyyouth-server']) { 
                    sh '''
                        # Create SSH directory if it doesn't exist
                        mkdir -p ~/.ssh
                        chmod 700 ~/.ssh
                        
                        # Add remote host to known_hosts
                        ssh-keyscan -H ${REMOTE_HOST} >> ~/.ssh/known_hosts
                        
                        python3 -m pip install setuptools-scm
                        python3 -c "import setuptools_scm; print(setuptools_scm.get_version())" > version.txt

                        # Rsync files to remote host
                        rsync -avz --delete \
                            --exclude='.git' \
                            --exclude='Jenkinsfile' \
                            --exclude='*.log' \
                            --exclude='*venv*' \
                            --exclude='*.pyc' \
                            ./ ${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_PATH}/
                    '''
                }
            }
        }

        stage('Download Dependencies') {
            steps {
                sshagent(['stanthonyyouth-server']) { 
                    sh '''
                        ssh ${REMOTE_USER}@${REMOTE_HOST} " \
                            # Add remote host to known_hosts
                            ssh-keyscan -H ${REMOTE_HOST} >> ~/.ssh/known_hosts
                            
                            cd ${REMOTE_PATH} && \
                            rm -rf ${VENV_DIR} && \

                            python3 -m venv ${VENV_DIR} && \
                            ${VENV_DIR}/bin/python -m pip install --upgrade pip && \
                            ${VENV_DIR}/bin/python -m pip install -r requirements.txt
                        "
                    '''
                }
            }
        }

        stage('Restart Service') {
            steps {
                sshagent(['stanthonyyouth-server']) { 
                    sh '''
                        # Add remote host to known_hosts
                        ssh-keyscan -H ${REMOTE_HOST} >> ~/.ssh/known_hosts
                        
                        ssh ${REMOTE_USER}@${REMOTE_HOST} " \
                            sudo /bin/systemctl restart say-backend.service
                        "
                    '''
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

