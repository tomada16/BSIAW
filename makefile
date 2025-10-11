bsiaw:
	-docker container rm -f $@
	docker build -t $@ .
	docker run -d --rm --name $@ -p 7708:80 $@:latest

connect:
	docker exec -it bsiaw sh
