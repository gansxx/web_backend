#生产环境FC快速镜像推送+
cd ..
docker build --tag gansxx053/web_backend_ali_fc:prod .
docker push gansxx053/web_backend_ali_fc:prod