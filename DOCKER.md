
# Build Image
# -t = "tag": What to call the image created from Dockerfile.
docker build -t doozy-app .

# Storage
There are a few files the server needs access to.  It needs the database, and it needs the .env file.
If the database is a SQLite DB then the "database.db" file needs to be accessible.  If the database
is postgres then that'll be running in a different container, and the .env file will point to it.

## Mount the Files
There are two was to get database.db (SQLite) and .env into the container.  The first is to mount
those files directly from their current location.  This is pretty straightforward: just use the
"--mount" option for each file.  The nice thing about "--mount" and using the actual files is that
it's easy to look at things while the container is running.

The command to do so is:
docker run --rm -p 8000:8000 --mount type=bind,source=./database.db,target=/server/database.db --mount type=bind,source=./.env,target=/server/.env,readonly doozy-app

For debugging we can use the following (this creates a shell where we can manually start doozy):
docker run --rm -p 8000:8000 -it --mount type=bind,source=./database.db,target=/server/database.db --mount type=bind,source=./.env,target=/server/.env,readonly doozy-app /bin/bash
uv run fastapi run src/app/main.py

## Create Volumes
Volumes are a distinct Docker entity that are managed by the daemon and not exposed directly to the
user.  There are advantages to using volumes (they can be copied between hosts).  But there are big
disadvantages too.  Namely, it's hard to pre-populate a volume with the contents we want.  We basically
have to copy the contents into either the image (into the location where the volume will be mounted),
or copy teh contents into the volume itself (which is a hassle).

We don't want to copy things into the image.  The whole idea is to be able to manage database.db and
the .env file independently of the image.  Copying them into the volume might be ok but still kind
of sucks, as there's no "docker volume cp" command.  Google if you want to know how to do it, but it
seems silly.

If volumes are used there are different ways to mount them.  The simplest way is to use the "-v" arg:
docker run --rm -p 8000:8000 -v database.db:/server/database.db -v .env:/server/.env:ro doozy-app

The "--mount" option can also be used (with "type=volume") and is the recommended way to mount a
volume because there are a lot more options to control things.  I don't use volumes yet, and maybe I
never will.

# Debugging
To attach to a running container use:
docker exec -it <id> /bin/bash

You can get the container id using:
docker ps

The debug commands will fail because the debug dependencies won't be in the container.  Update the
Dockerfile to add them with:
RUN uv sync --locked
docker build -t doozy-app .

The audio system library also won't be in the container.  To add it use:
apt-get update
apt-get install libportaudio2
apt-get install vim  # You'll want this too...
apt-get install postgresql-client  # And maybe this...

psql -h db -p 5432 -U doozy
\d : Show tables

# Docker Compose

docker compose up [-d]: Builds, re-creates, starts, attaches containers for a service.
docker compose start: Restarts existing containers for a service.

docker compose down:
docker compose stop: 
