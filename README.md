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

