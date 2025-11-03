source ../.env
export ALICLOUD_ACCESS_KEY=$ALICLOUD_ACCESS_KEY                                                         
export ALICLOUD_SECRET_KEY=$ALICLOUD_SECRET_KEY
echo "if you not init,please run terraform init and terraform plan"

terraform apply -auto-approve

echo "run terraform destroy auto-approve to delete preview machine"