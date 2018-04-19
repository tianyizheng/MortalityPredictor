pipeline{
    agent any

    stages {
        stage('Deploy') {
            steps{
                //The Jenkins Declarative the Pipeline does not provide functionality to deploy to a private
                //Docker registry. In order to deploy to the HDAP Docker registry we must write a custom Groovy
                //script using the Jenkins Scripting Pipeline. This is done by placing Groovy code with in a "script"
                //element. The script below registers the HDAP Docker registry with the Docker instance used by
                //the Jenkins Pipeline, builds a Docker image of the project, and pushes it to the registry.
                script{
                    docker.withRegistry('https://apps2.hdap.gatech.edu'){
                        def applicationImage = docker.build("MortalityPredictor:1.0","-f Dockerfile .")
                        applicationImage.push('latest')
                    }
                }
            }
        }
    }

}