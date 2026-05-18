from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class Profile(models.Model):
    ROLE_CHOICES = [
        ('student', '學生'),
        ('teacher', '老師'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, verbose_name="使用者")
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, verbose_name="角色")

    def __str__(self):
        return f"{self.user.username} - {self.get_role_display()}"

    class Meta:
        verbose_name = "使用者資料"
        verbose_name_plural = "使用者資料"


class Course(models.Model):
    title = models.CharField(max_length=200, verbose_name="課程名稱")
    teacher = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="講師")
    price = models.IntegerField(verbose_name="價格")
    description = models.TextField(verbose_name="課程介紹")
    image = models.ImageField(
        upload_to='course_images/',
        verbose_name="課程圖片",
        blank=True,
        null=True
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="建立時間")

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = "課程"
        verbose_name_plural = "課程管理"


class Enrollment(models.Model):
    student = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="學生")
    course = models.ForeignKey(Course, on_delete=models.CASCADE, verbose_name="課程")
    purchased_at = models.DateTimeField(auto_now_add=True, verbose_name="購買時間")

    def __str__(self):
        return f"{self.student.username} - {self.course.title}"

    class Meta:
        verbose_name = "購課紀錄"
        verbose_name_plural = "購課紀錄"
        unique_together = ('student', 'course')


class LearningRecord(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="使用者")
    course = models.ForeignKey(Course, on_delete=models.CASCADE, verbose_name="課程")
    minutes = models.PositiveIntegerField(default=30, verbose_name="觀看分鐘數")
    watched_at = models.DateTimeField(auto_now_add=True, verbose_name="觀看時間")

    def __str__(self):
        return f"{self.user.username} - {self.course.title} - {self.minutes} 分鐘"

    class Meta:
        verbose_name = "學習紀錄"
        verbose_name_plural = "學習紀錄"


class Coupon(models.Model):
    DISCOUNT_TYPE_CHOICES = [
        ('amount', '固定金額折扣'),
        ('percent', '百分比折扣'),
    ]

    code = models.CharField(max_length=50, unique=True, verbose_name="優惠碼")
    name = models.CharField(max_length=100, verbose_name="優惠券名稱")
    discount_type = models.CharField(
        max_length=20,
        choices=DISCOUNT_TYPE_CHOICES,
        verbose_name="折扣類型"
    )
    discount_value = models.PositiveIntegerField(verbose_name="折扣數值")
    min_spend = models.PositiveIntegerField(default=0, verbose_name="最低消費金額")
    start_date = models.DateTimeField(verbose_name="開始時間")
    end_date = models.DateTimeField(verbose_name="結束時間")
    usage_limit = models.PositiveIntegerField(default=0, verbose_name="總使用次數限制，0代表不限")
    is_active = models.BooleanField(default=True, verbose_name="是否啟用")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="建立時間")

    def __str__(self):
        return f"{self.code} - {self.name}"

    def is_valid_now(self):
        now = timezone.now()
        if not self.is_active:
            return False
        if self.start_date > now:
            return False
        if self.end_date < now:
            return False
        if self.usage_limit > 0:
            used_count = self.usages.count()
            if used_count >= self.usage_limit:
                return False
        return True

    def calculate_discount(self, price):
        if price < self.min_spend:
            return 0

        if self.discount_type == 'amount':
            discount = self.discount_value
        elif self.discount_type == 'percent':
            discount = int(price * self.discount_value / 100)
        else:
            discount = 0

        if discount > price:
            discount = price

        return discount

    class Meta:
        verbose_name = "優惠券"
        verbose_name_plural = "優惠券管理"


class Order(models.Model):
    STATUS_CHOICES = [
        ('paid', '已付款'),
        ('cancelled', '已取消'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="購買者")
    course = models.ForeignKey(Course, on_delete=models.CASCADE, verbose_name="課程")
    coupon = models.ForeignKey(
        Coupon,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        verbose_name="使用優惠券"
    )
    original_price = models.PositiveIntegerField(verbose_name="原價")
    discount_amount = models.PositiveIntegerField(default=0, verbose_name="折扣金額")
    final_price = models.PositiveIntegerField(verbose_name="實付金額")
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='paid',
        verbose_name="訂單狀態"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="建立時間")

    def __str__(self):
        return f"{self.user.username} - {self.course.title} - NT$ {self.final_price}"

    class Meta:
        verbose_name = "訂單"
        verbose_name_plural = "訂單管理"


class CouponUsage(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="使用者")
    coupon = models.ForeignKey(
        Coupon,
        on_delete=models.CASCADE,
        related_name="usages",
        verbose_name="優惠券"
    )
    order = models.OneToOneField(Order, on_delete=models.CASCADE, verbose_name="訂單")
    discount_amount = models.PositiveIntegerField(verbose_name="實際折扣金額")
    used_at = models.DateTimeField(auto_now_add=True, verbose_name="使用時間")

    def __str__(self):
        return f"{self.user.username} 使用 {self.coupon.code}"

    class Meta:
        verbose_name = "優惠券使用紀錄"
        verbose_name_plural = "優惠券使用紀錄"