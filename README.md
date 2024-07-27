1. 安装需要的包
```
pip install -r requirements.txt
```
2. 注册backpack 拿到API Key 和Secrets 

如果对你有帮助，可以用我的注册链接：
https://backpack.exchange/refer/398b43e3-1984-47e2-902b-11bc08450687 

注册完成之后在Settings > API Keys > New API Key 可以创建新的API Key 和Secret 

+ 需要给读写的权限
+ 建议只放你想跑脚本的钱，和你做其他交易的账户分开

3. 文件修改 
simple_grid L28 添加自己的api key 和secret 

4. 运行程序
python simple_grid.py 

建议使用pm2， 会帮助管理脚本的运行，遇到错误会自动重启。 