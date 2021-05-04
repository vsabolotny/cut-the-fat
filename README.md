# Hello node on kubernetes
This is a very simple application written with node.js, running on docker and kubernetes, as a database we are using mongodb. 

This application is a challenge assignment in the course https://www.udemy.com/course/docker-kubernetes-the-practical-guide/ which I can highly recommend if you want to learn docker and kubernetes.

# Services
Both services user and task are using the service auth for authentification. Service auth is not reachable from the outside but only by the services user and task.

For more take a look into the API's.

# Prepare installation
You can run the application with docker-compose or kubernetes. 

Make sure the mongodb connection URI is correct added in 
- docker-compose.yaml
- kubernetes/tasks.yaml
- kubernetes/users.yaml

Here you can run docker with
```
$ docker-compose up -d --build
```

# Kuberetes 
Create 3 images of the services user, task and auth. Push them to your docker hub. 

Replace docker hub repositories in the kubernetes yaml configs.

## Kubernetes locally with minikube
Install minikube for running the kubernetes cluster on your local mashine https://minikube.sigs.k8s.io/docs/start/.

Apply kubernetes configs to start deployments, services etc.

```
& cd kubernetes
$ kubectl apply -f=auth.yaml,tasks.yaml,users.yaml
```

Get the URL of the user service as example
```
$ minikube service users-service
```

Open the dashboard of your kubernetes cluster
```
$ minikube dashboard
```

## Kubernetes AWS EKS
Create cluster on the EKS. 

Create nodes in the cluster.

Create NFS volume.

Generate the config and replace the config in the <user>/.kube/ on Mac.

Now just use kubectl as you are locally
```
& cd kubernetes
$ kubectl apply -f=auth.yaml,tasks.yaml,users.yaml
```

Get the URL of the user service as example
```
$ minikube service users-service
```

# Test with postman
Import the postman-collection.json. There you can find some test cases.

# Cleanup 
## AWS kubernetes
The simplest way to do a cleanup on the AWS EKS over the aws-cli tool. Follow the instructions https://docs.aws.amazon.com/eks/latest/userguide/delete-cluster.html.

## Locally kubernetes
Delete in the same way as create
```
& cd kubernetes
$ kubectl delete -f=auth.yaml,tasks.yaml,users.yaml
```

## Docker-compose
Putting down will delete the container and -v will delete also the volumes.
```
$ docker-compose down -v
```

Delete imges which are not used right now
```
$ docker image prune
```
