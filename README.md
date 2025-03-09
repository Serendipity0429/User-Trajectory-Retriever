# User-Trajectory-Retriever
To retrieve user trajectories in different authentic tasks.

[![THUIR](https://img.shields.io/badge/THUIR-ver%201.0-blueviolet)](http://www.thuir.cn)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](./LICENSE)
[![made-with-python](https://img.shields.io/badge/Made%20with-Python-red.svg)](#python)
[![made-with-js](https://img.shields.io/badge/Made%20with-JS-yellow.svg)](#javascript)
![Static Badge](https://img.shields.io/badge/made_by-Zhang_Xinkai-blue)

## Introduction

## Overview

## List of Recorded Information

You can add or delete any function on your need.

## Environment compatibility  

## Support
Fow now, this toolkit only support the logging on Baidu and Sogou, which are two largest commercial search engines in China. We welcome anyone to implement the support for more search engines such as Google, Bing, Yahoo, and Naver.

## How to launch
First you need to initialize the database of Django backend.
```bash
python manage.py makemigrations user_system
python manage.py makemigrations task_manager
python manage.py migrate
```
* You can then launch the django backend with the following command:
```bash
python manage.py runserver 0.0.0.0:8000
```
* Install the chrome extension on your Google chrome. (or other browsers that support chrome extension)

* Login at the annotation platform (0.0.0.0:8000) and register a new account.

* Click the extension logo and login with the account.


* Then you can start your retrieval!

## Some things you should notice
* The baseURL in the extension should be the same with the base URL of the annotation platform.
```javascript
var baseUrl = "http://127.0.0.1:8000";
```  
* You should ensure that the chrome extention is on before the search, or nothing will be recorded.  



* There may be problems in query recording if search users submit queries very frequently, e.g., submit two queries within 1 second. Please ask the participants to search with normal speed. We also welcome anyone to fix this bug.
* Each query that has been recorded should be annotated within **48** hours, or they will be removed in case that users have forgotten the search details.
* It is normal to have error as follows when submitting the annotations for a query. Just return the previous page and submit again.

<p align="center">
  <img src="https://github.com/xuanyuan14/Web-Search-Field-Study-Toolkit/blob/master/images/error.png">
</p>

* For Baidu, you should 1) shut down the instant predicton function, and 2) set all SERPs to be opened in a new window. Without these settings, search pages will be updated merely by in-page javascript functions and our toolkit will fail to record correct information. 

<p align="center">
  <img src="https://github.com/xuanyuan14/Web-Search-Field-Study-Toolkit/blob/master/images/close.png">
</p>

<p align="center">
  <img src="https://github.com/xuanyuan14/Web-Search-Field-Study-Toolkit/blob/master/images/setting.png">
</p>

## Citation


## Contact
If you have any questions, please feel free to contact me via [stevenzhangx@163.com]() or open an issue.

## Acknowledgement
This toolkit is built based on the prototype systems that were used in several previous work: 
* [Mao, Jiaxin, et al. "When does relevance mean usefulness and user satisfaction in web search?" Proceedings of the 39th International ACM SIGIR conference on Research and Development in Information Retrieval. 2016.](http://www.thuir.org/group/~YQLiu/publications/sigir2016Mao.pdf)
* [Wu, Zhijing, et al. "The influence of image search intents on user behavior and satisfaction." Proceedings of the Twelfth ACM International Conference on Web Search and Data Mining. 2019.](http://www.thuir.org/group/~YQLiu/publications/WSDM19Wu.pdf)
* [Zhang, Fan, et al. "Models versus satisfaction: Towards a better understanding of evaluation metrics." Proceedings of the 43rd International ACM SIGIR Conference on Research and Development in Information Retrieval. 2020.](https://static.aminer.cn/upload/pdf/1982/1327/2004/5f0277e911dc830562231df7_0.pdf)
* [Zhang, Fan, et al. "Cascade or recency: Constructing better evaluation metrics for session search." Proceedings of the 43rd International ACM SIGIR Conference on Research and Development in Information Retrieval. 2020.](http://www.thuir.cn/group/~mzhang/publications/SIGIR2020-ZhangFan1.pdf)
* [Chen, Jia, et al. "Towards a Better Understanding of Query Reformulation Behavior in Web Search." Proceedings of the Web Conference 2021.](https://dl.acm.org/doi/10.1145/3442381.3449916)

We thank the authors for their great work.
