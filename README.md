# Gitlab-Hub

_Gitlab project aggregator for evaluating team projects_

For more information fisit our [wiki](https://cognate.pages.taltech.ee/wiki/)

## Docker
- **run app**
```
docker-compose up
```
You should now have access to the app in [localhost](localhost:8000), but first you should create superuser in Django
--- 
- **enter django container and create superuser**
```
docker exec -it django bash
python3 manage.py migrate
python3 manage.py createsuperuser
```
- **run django-admin command in container**
```
docker-compose run django django-admin
```
- **Postgres**
```
docker exec -it pgdb psql -U postgres
\c postgres
```

## To generate model picture
```
python3 manage.py graph_models --pydot -a -g -o pic.png
```

## To setup CI / CD on new server
- Install docker on server
  - https://docs.docker.com/engine/install/ubuntu/
- Install docker-compose on server
  - https://docs.docker.com/compose/install/
- Install gitlab runner on server
  - https://stackoverflow.com/questions/65206569/getting-docker-error-while-using-shell-gitlab-runner-erro0000
  - https://docs.gitlab.com/runner/install/linux-manually.html
  - https://gitlab-runner-downloads.s3.amazonaws.com/latest/index.html
  - https://unix.stackexchange.com/questions/12453/how-to-determine-linux-kernel-architecture
- Register gitlab runner
  - use command `sudo gitlab-runner register`
  - tag needs to be the same as the tag in .gitlab-ci.yml
  - url and token can be acquired from https://gitlab.cs.ttu.ee/cognate/back/-/settings/ci_cd#js-runners-settings
- Configure permissions and stuff
  - Make sure that /home/gitlab-runner is owned by gitlab-runner
  - Make sure that /etc/gitlab-runner/config.toml roughly matches the files in other servers
  - Make sure that gitlab-runner has sudo right and doesn't require password
    - https://stackoverflow.com/questions/19383887/how-to-use-sudo-in-build-script-for-gitlab-ci
- Docker complains about network connectivity
  - If during the docker build, it starts complaining about network connectivity
  - Try following this: https://stackoverflow.com/questions/24832972/docker-apt-get-update-fails
