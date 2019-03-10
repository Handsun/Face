import hashlib
import datetime

from django.shortcuts import render
from django.shortcuts import redirect

from django.conf import settings
from login import models
from login import forms
from login import face
import json
# Create your views here.


def hash_code(s, salt='mysite'):# 加点盐
    h = hashlib.sha256()
    s += salt
    h.update(s.encode())  # update方法只接收bytes类型
    return h.hexdigest()

def index(request):
    request.session['index_active'] = 'active'
    request.session['detect_active'] = 'inactive'
    return render(request,'login/index.html')


def login(request):
    if request.session.get('is_login',None):
        return  redirect('/index/')

    if request.method == 'POST':

        login_form = forms.UserForm(request.POST)
        message = ""

        if login_form.is_valid():
            username = login_form.cleaned_data['username']
            password = login_form.cleaned_data['password']

            try:
                user = models.User.objects.get(name=username)
                if not user.has_confirmed:
                    message = '该用户还未通过邮件确认！'
                    return render(request,'login/login.html',locals())
                if user.password == hash_code(password):
                    request.session['is_login'] = True
                    request.session['user_id'] = user.id
                    request.session['user_name'] = user.name
                    return redirect('/index/')
                else:
                    message = "密码不正确！"
            except:
                message = "用户名不存在！"

        return render(request, 'login/login.html', locals())

    login_form = forms.UserForm()
    return render(request,'login/login.html',locals())


def make_confirm_string(user):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    code = hash_code(user.name,now)
    models.ConfirmString.objects.create(code=code,user=user)
    return code

def send_email(email,code):
    from django.core.mail import EmailMultiAlternatives

    subject = '注册确认邮件'

    text_content = '''感谢注册www.liujiangblog.com，这里是刘江的博客和教程站点，专注于Python和Django技术的分享！\
                       如果你看到这条消息，说明你的邮箱服务器不提供HTML链接功能，请联系管理员！'''

    html_content = '''
                       <p>感谢注册<a href="http://{}/confirm/?code={}" target=blank>www.liujiangblog.com</a>，\
                       这里是刘江的博客和教程站点，专注于Python和Django技术的分享！</p>
                       <p>请点击站点链接完成注册确认！</p>
                       <p>此链接有效期为{}天！</p>
                       '''.format('127.0.0.1:8000', code, settings.CONFIRM_DAYS)
    msg = EmailMultiAlternatives(subject, text_content, settings.EMAIL_HOST_USER, [email])
    msg.attach_alternative(html_content, "text/html")
    msg.send()

def register(request):
    if request.session.get('is_login',None):
        return  redirect('/index/')

    if request.method == 'POST':
        register_form = forms.RegisterForm(request.POST)
        message = ""

        if register_form.is_valid():
            username = register_form.cleaned_data['username']
            password1 = register_form.cleaned_data['password1']
            password2 = register_form.cleaned_data['password2']
            email = register_form.cleaned_data['email']
            sex = register_form.cleaned_data['sex']

            if password1 != password2:
                message = "两次输入的密码不同！"
                return render(request,'login/register.html',locals())
            else:
                same_name_user = models.User.objects.filter(name=username)
                if same_name_user:
                    message = "用户已存在，请重新选择用户名！"
                    return  render(request,'login/register.html',locals())
                same_email_user = models.User.objects.filter(email=email)
                if same_email_user:
                    message = "该邮箱地址已被注册，请使用其他邮箱！"
                    return render(request,'login/register.html',locals())

                new_user = models.User()
                new_user.name = username
                new_user.password = hash_code(password1)
                new_user.email = email
                new_user.sex = sex
                new_user.save()

                code = make_confirm_string(new_user)
                return  redirect('/login/')
    register_form = forms.RegisterForm()
    return render(request,'login/register.html',locals())

def logout(request):
    if not request.session.get('is_login',None):
        return redirect('/index/')
    request.session.flush()
    return redirect("/index/")

def user_confirm(request):
    code = request.GET.get('code',None)
    message = ''
    try:
        confirm = models.ConfirmString.objects.get(code=code)
    except:
        message = '无效的确认请求！'
        return render(request,'login/confirm.html',locals())

    c_time = confirm.c_time
    now = datetime.datetime.now()
    if now > c_time + datetime.timedelta(settings.CONFIRM_DAYS):
        confirm.user.delete()
        message = '您的邮件已经过期！请重新注册！'
        return render(request,'login/confirm.html',locals())
    else:
        confirm.user.has_confirmed = True
        confirm.user.save()
        confirm.delete()
        message = '感谢确认，请使用账户登录！'
        return render(request,'login/confirm.html',locals())


def detect(request):
    request.session['index_active'] = 'inactive'
    request.session['detect_active'] = 'active'
    if request.session.get('is_login', None):
        if request.method == 'GET':
            return render(request, 'login/detect.html', locals())

        if request.method == 'POST':
            file = request.FILES.get('file',None)
            file_path = settings.IMAGE_ROOT + file.name
            with open(file_path,'wb') as f:
                for i in file.chunks():
                    f.write(i)
            file_src = file.name
            result = json.loads(face.FaceDetect(file_path))['faces'][0]['attributes']
            keys = ['emotion', 'gender', 'age', 'mouthstatus', 'glass', 'skinstatus', 'smile', 'eyestatus', 'ethnicity']
            image_result = {
                'emotion':'',
                'gender': '',
                'age': '',
                'glass': '',
                'smile': '',
                'ethnicity':''
            }
            if not result is None:
                for key in keys:
                    if key == 'age' and result[key]['value']:
                        image_result[key] = result[key]['value']

                    if key == 'gender' and result[key]['value']:
                        if result[key]['value'] == 'Male':
                            image_result[key] = '男'
                        elif result[key]['value'] == 'Female':
                            image_result[key] = '女'
                        else:
                            image_result[key] = '未知'

                    if key == 'glass' and result[key]['value']:
                        if result[key]['value'] == 'Dark':
                            image_result[key] = '戴墨镜'
                        elif result[key]['value'] == 'Normal':
                            image_result[key] = '戴眼镜'

                    if key == 'ethnicity' and result[key]['value']:
                        if result[key]['value'] == 'ASIAN':
                            image_result[key] = '亚洲人'
                        elif result[key]['value'] == 'WHITE':
                            image_result[key] = '白人'
                        elif result[key]['value'] == 'BLACK':
                            image_result[key] = '黑人'

                    if key == 'smile' and result[key]['value']:
                        if result[key]['value'] > result[key]['threshold']:
                            image_result[key] = '微笑'

                    if key == 'emotion':
                        emotion = max(result[key],key=result[key].get)
                        if emotion == 'surprise':
                            image_result[key] = '惊讶'
                        elif emotion == 'amger':
                            image_result[key] = '愤怒'
                        elif emotion == 'disgust':
                            image_result[key] = '厌恶'
                        elif emotion == 'fear':
                            image_result[key] = '恐惧'
                        elif emotion == 'happiness':
                            image_result[key] = '高兴'
                        elif emotion == 'neutral':
                            image_result[key] = '平静'
                        elif emotion == 'sadness':
                            image_result[key] = '伤心'
            return render(request, 'login/detect.html', locals())
    else:
        return redirect('/login/')
