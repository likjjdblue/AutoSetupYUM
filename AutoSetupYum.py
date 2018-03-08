#!/usr/bin/env python
#-*- encoding:utf-8 -*-

import subprocess
from os import path,mkdir
from os import geteuid
from sys import exit
import re
import socket

TextColorRed='\x1b[31m'
TextColorGreen='\x1b[32m'
TextColorWhite='\x1b[0m'


def checkRootPrivilege():
###  检查脚本的当前运行用户是否是 ROOT ###
  RootUID=subprocess.Popen(['id','-u','root'],stdout=subprocess.PIPE).communicate()[0]
  RootUID=RootUID.strip()
  CurrentUID=geteuid()
  return str(RootUID)==str(CurrentUID)


def __checkOSVersion():
#### 检查操作系统的版本，确保是Centos 7 的版本 ###
    OSInfoFileList=['/etc/centos-release']
    for filepath in OSInfoFileList:
      if path.isfile(filepath):
         TmpFileObj=open(filepath,mode='r')
         FileContent=TmpFileObj.read()
         FileContent=FileContent.strip()
         TmpFileObj.close()
         ReObj=re.search(r'\s+([\d\.]+)\s+',FileContent)
         if ReObj and ('CentOS' in FileContent):
            OSVersion=ReObj.group(1)
            if re.search(r'^7.*',OSVersion):
               print (TextColorGreen+'操作系统满足要求!'+TextColorWhite)
               return 0
            else:
               print (TextColorRed+'操作系统不满足要求(需要CentOS7)，当前系统:'+str(FileContent)+'\n程序退出!'+TextColorWhite)
               exit(1)
    print (TextColorRed+'无法获取操作系统版本信息，或者版本不符合要求(需要CentOS7)'+'\n程序退出!'+TextColorWhite)
    exit(1)

def checkPortState(host='127.0.0.1',port=9200):
### 检查对应服务器上面的port 是否处于TCP监听状态 ##

    s=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
    s.settimeout(1)
    try:
       s.connect((host,port))
       return {'RetCode':0,
               'Result':TextColorGreen+str(host)+':'+str(port)+'处于监听状态'+TextColorWhite}
    except:
       return {'RetCode':1,
               'Result':TextColorRed+'无法访问'+str(host)+':'+str(port)+TextColorWhite}



def setupLocalYumRepo():
    if not path.isfile(r'Packages.tar'):
       print (TextColorRed+'当前目录下未检测到"Packages.tar"文件，无法继续安装，程序退出!'+TextColorWhite)
       exit(1)

    if path.isfile(r'/YUMData'):
       print (TextColorRed+'/YUMData 是一个文件，无法创建同名的文件夹。程序退出.'+TextColorWhite)
       exit(1)

    try:
       mkdir(r'/YUMData')
    except:
       pass
    finally:
       print (TextColorGreen+'/YUMData 目录已经创建完成'+TextColorWhite)

    print ('即将解压压缩文件，请稍后........')
    
    if subprocess.call('tar -C /YUMData -xvf Packages.tar',shell=True):
       print (TextColorRed+'解压Packages.tar失败，程序退出'+TextColorWhite)
       exit(1)
    print (TextColorGreen+'压缩包解压完成.'+TextColorWhite)

    if subprocess.call('rpm -Uvh --replacepkgs rpm_package/createrepo/*.rpm',shell=True):
       print (TextColorRed+'安装 createrepo 失败，程序退出.'+TextColorWhite)
       exit(1)
    print (TextColorGreen+'成功安装 createrepo'+TextColorWhite)

    print ('即将构建本地YUM 源，请耐心等待.....')
    if subprocess.call('createrepo -v /YUMData/Packages',shell=True):
       print (TextColorRed+'构建本地YUM 源失败，程序退出.'+TextColorWhite)
       exit(1)
    print (TextColorGreen+'成功构建本地YUM源'+TextColorWhite)


    print ('即将配置本地YUM源,请稍候......')
    if subprocess.call('cp conf/TRSLocalRepo.repo /etc/yum.repos.d',shell=True):
       print (TextColorRed+'拷贝 TRSLocalRepo.repo 文件失败，程序退出'+TextColorWhite)

    if subprocess.call('yum install --disablerepo="*" --enablerepo="trslocalrepo" yum-utils -y',shell=True):
       print (TextColorRed+'安装 yum-utils 组件失败，程序退出'+TextColorWhite)

    if subprocess.call('yum-config-manager --disable \*',shell=True):
       print (TextColorRed+'禁用默认YUM 失败，程序退出'+TextColorWhite)
       exit(1)

    if subprocess.call('yum-config-manager --enable trslocalrepo',shell=True):
       print (TextColorRed+'启用本地 YUM  失败，程序退出.'+TextColorWhite)

    subprocess.call('yum clean all',shell=True)
    subprocess.call('rm -rf /var/cache/yum',shell=True)
    subprocess.call('yum update',shell=True)

    print (TextColorGreen+'本地YUM 源配置完成.'+TextColorWhite)

    print ('即将安装apache,请稍候.....')
    if subprocess.call('yum install httpd -y',shell=True):
       print (TextColorRed+'安装apache失败，程序退出.'+TextColorWhite)

    subprocess.call('cp -n /etc/httpd/conf/httpd.conf /etc/httpd/conf/httpd.conf.backup',shell=True)
    subprocess.call('cat conf/httpd.conf >/etc/httpd/conf/httpd.conf',shell=True)

    subprocess.call('chown -R apache:apache /YUMData',shell=True)
    subprocess.call('chcon -R -t httpd_sys_content_t /YUMData',shell=True)

    subprocess.call('setenforce 0',shell=True)
    subprocess.call('firewall-cmd --zone=public --add-port=18888/tcp --permanent',shell=True)
    print (TextColorGreen+'成功安装apache.\n现在可以新建一个SSH 连接,并运行systemctl start httpd.'+TextColorWhite)


def addRemoteYumRepo():
    TmpIP=raw_input('其请输入局域网中搭建的YUM源服务器IP地址：')
    TmpIP=TmpIP.strip()
    TmpResult=checkPortState(TmpIP,18888)
    
    if TmpResult['RetCode']!=0:
       print (TextColorRed+'无法访问 '+TmpIP+':18888 端口，\n无法使用本地搭建的YUM源,请确保已经搭建了本地YUM源,\n且apache进程处于运行状态;.'+TextColorWhite)
       print (TextColorRed+'程序退出!\n'+TextColorWhite)
       exit(1)

    print ('即将配置添加本地YUM源，请稍候.....')
   
    with open(r'conf/TRSRemoteRepo.repo') as f:
       TmpFileContent=f.read()


    TmpFileContent=re.sub(r'(^baseurl=http://)(.*?)\n','\g<1>'+str(TmpIP)+':18888\n',TmpFileContent,flags=re.MULTILINE)
    
    with open(r'/etc/yum.repos.d/TRSRemoteRepo.repo','w') as f:
        f.write(TmpFileContent) 
          

    if subprocess.call('yum install --disablerepo="*" --enablerepo="trsremoterepo" yum-utils -y',shell=True):
       print (TextColorRed+'安装 yum-utilis 失败，程序退出'+TextColorWhite)

    subprocess.call('yum-config-manager --disable \*',shell=True)
    subprocess.call('yum-config-manager --enable trs\*',shell=True)

    subprocess.call('yum clean all',shell=True)
    subprocess.call('rm -rf /var/cache/yum',shell=True)
    subprocess.call('yum update',shell=True)

    print (TextColorGreen+'成功添加本地YUM 源.'+TextColorWhite)



def  restoreOriginalYUM():
     subprocess.call('yum-config-manager --enable \*',shell=True)
     subprocess.call('yum-config-manager --disable trs\*',shell=True)
     subprocess.call('yum clean all',shell=True)
     subprocess.call('rm -rf /var/cache/yum',shell=True)
     subprocess.call('yum update',shell=True)

     print (TextColorGreen+'已经成功恢复默认YUM配置.'+TextColorWhite)


def mainStart():
    __checkOSVersion()
    if not checkRootPrivilege():
       print (TextColorRed+'请使用ROOT 账号运行本工具，程序退出.'+TextColorWhite)
       exit(1)

    while True:
       print (TextColorGreen+'#########  欢迎使用“海云系统”，本工具将帮助你在局域环境中搭建YUM 源。  ######')
       print ('说明:')
       print ('     只有在本地Centos服务器无法访问互联网的情况下才需要搭建本地YUM源，否则就不需要搭建；')
       print ("     另外，本地YUM源只需要搭建在局域网中其中一台服务器上即可，不需要重复搭建；其他服务器只要能访问该服务器即可。")
       print ('           1、搭建本地YUM源;')
       print ('           2、添加本地YUM源；')
       print ('           3、恢复系统默认YUM源；')
       print ('           0、退出；'+TextColorWhite)

       choice=raw_input('请输入数值序号:')
       choice=choice.strip()


       if choice=='1':
          setupLocalYumRepo()
       elif choice=='2':
          addRemoteYumRepo()
       elif choice=='3':
          restoreOriginalYUM()
       elif choice=='0':
          exit(0)



    

    
     
       
#setupLocalYumRepo()
mainStart()
#addRemoteYumRepo()
