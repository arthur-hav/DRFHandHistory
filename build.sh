sudo docker-compose build
sudo docker-compose run --rm app pytest -p no:cacheprovider
#sudo docker-compose run --rm app python3 manage.py makemigrations
#sudo docker-compose run --rm app python3 manage.py migrate
#sudo docker-compose run --rm app python manage.py createsuperuser


