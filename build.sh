export DJANGO_DB_SALT=keyring get tricky salt
export POSTGRES_PASSWORD=keyring get tricky db
export DJANGO_SUPERUSER_PASSWORD=keyring get tricky django

#sudo docker-compose build
#sudo docker-compose run --rm app python3 manage.py makemigrations
#sudo docker-compose run --rm app python3 manage.py migrate
#sudo docker-compose run --rm app python manage.py createsuperuser
sudo docker-compose run --rm app pytest --cov=pokerapp ./tests/ --import-mode importlib -p no:cacheprovider -vv
sudo docker-compose run --rm app coverage run
