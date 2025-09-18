# TODO:集成所有节点中的用户数据，并生成一个总的用户数据文件
from vps_vultur_manage import list_instances
instances=list_instances()
#TODO: 遍历所有节点，获取每个节点的用户数据文件，并合并
ip_list=[]