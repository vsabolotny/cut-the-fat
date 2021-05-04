# Hello node on kubernetes
This is a very simple application written with node.js, running on docker and kubernetes, as a database we are using mongodb. 

This application is a challenge assignment in the course https://www.udemy.com/course/docker-kubernetes-the-practical-guide/ which I can highly recommend if you want to learn docker and kubernetes.

# Services
Both services user and task are using the service auth for authentification. Service auth is not reachable from the outside but only by the services user and task.

For more take a look into the API's.

# Installation
You can run the application with docker-compose or kubernetes. 

Make sure the mongodb connection URI is correct added in 
- docker-compose.yaml
- kubernetes/tasks.yaml
- kubernetes/users.yaml

Here you can run docker with
```
$ docker-compose up -d --build
```

## Kubernetes localy
Create 3 images of the services user, task and auth. Push them to the docker hub. 