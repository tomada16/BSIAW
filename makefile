# Run docker compose
# Copyright (c) 2025 Politechnika Wrocławska

all:
	cd docker && docker-compose down --rmi all -v; docker-compose up

URL = 139073842005.dkr.ecr.eu-north-1.amazonaws.com/tomada16/bsiaw
ECR = $(URL):latest

aws:
	docker build -t tomada16/bsiaw .
	docker tag tomada16/bsiaw:latest $(ECR)
	docker push $(ECR)
	cosign sign --key bsiaw-key.key $(ECR)
