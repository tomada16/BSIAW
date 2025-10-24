# Run docker compose
# Copyright (c) 2025 Politechnika Wrocławska

all:
	cd docker && docker-compose down --rmi all -v; docker-compose up
