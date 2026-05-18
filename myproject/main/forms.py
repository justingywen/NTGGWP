from django import forms
from django.contrib.auth.models import User
from .models import Course


class CourseForm(forms.ModelForm):
    class Meta:
        model = Course
        fields = ['title', 'price', 'description', 'image']


class RegisterForm(forms.Form):
    username = forms.CharField(label='帳號', max_length=150)
    email = forms.EmailField(label='Email')
    password = forms.CharField(label='密碼', widget=forms.PasswordInput)
    confirm_password = forms.CharField(label='確認密碼', widget=forms.PasswordInput)

    ROLE_CHOICES = [
        ('student', '學生'),
        ('teacher', '老師'),
    ]

    role = forms.ChoiceField(label='身分', choices=ROLE_CHOICES)

    def clean_username(self):
        username = self.cleaned_data['username']
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError('這個帳號已經被使用了。')
        return username

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')

        if password and confirm_password and password != confirm_password:
            raise forms.ValidationError('兩次輸入的密碼不一致。')

        return cleaned_data


class CouponApplyForm(forms.Form):
    coupon_code = forms.CharField(
        label='優惠碼',
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': '請輸入優惠碼，沒有可留空'
        })
    )