# Run docker compose
# Copyright (c) 2025 Politechnika Wrocławska

all:
	cd docker && docker-compose down --rmi all -v; docker-compose up

aws:
	docker build -t tomada16/bsiaw .
	docker tag tomada16/bsiaw:latest 139073842005.dkr.ecr.eu-north-1.amazonaws.com/tomada16/bsiaw:latest
	docker push 139073842005.dkr.ecr.eu-north-1.amazonaws.com/tomada16/bsiaw:latest

