bsiaw:
	-docker container rm -f $@
	docker build -t $@ .
	docker run -d --rm --name $@ -p 7708:80 -v $(shell pwd)/web:/srv/web $@:latest

connect:
	docker exec -it bsiaw sh
