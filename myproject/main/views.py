import csv
from django.http import HttpResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from .models import (
    Course,
    Profile,
    Enrollment,
    LearningRecord,
    Coupon,
    Order,
    CouponUsage,
)
from .forms import RegisterForm, CourseForm, CouponApplyForm


def home(request):
    courses = Course.objects.all()
    return render(request, 'main/home.html', {'courses': courses})


def course_detail(request, course_id):
    course = get_object_or_404(Course, id=course_id)

    already_purchased = False
    if request.user.is_authenticated:
        already_purchased = Enrollment.objects.filter(
            student=request.user,
            course=course
        ).exists()

    return render(request, 'main/course_detail.html', {
        'course': course,
        'already_purchased': already_purchased
    })


def register(request):
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = User.objects.create_user(
                username=form.cleaned_data['username'],
                email=form.cleaned_data['email'],
                password=form.cleaned_data['password']
            )

            Profile.objects.create(
                user=user,
                role=form.cleaned_data['role']
            )

            return redirect('register_success')
    else:
        form = RegisterForm()

    return render(request, 'main/register.html', {'form': form})


def register_success(request):
    return render(request, 'main/register_success.html')


def login_view(request):
    error_message = None

    if request.method == 'POST':
        login_input = request.POST.get('username')
        password = request.POST.get('password')

        if '@' in login_input:
            try:
                user_obj = User.objects.get(email=login_input)
                username = user_obj.username
            except User.DoesNotExist:
                username = login_input
        else:
            username = login_input

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)

            if user.is_superuser:
                return redirect('/admin/')

            try:
                profile = user.profile
                if profile.role == 'teacher':
                    return redirect('teacher_dashboard')
                elif profile.role == 'student':
                    return redirect('student_dashboard')
                else:
                    return redirect('home')
            except Profile.DoesNotExist:
                return redirect('home')
        else:
            error_message = '帳號 / Email 或密碼錯誤。'

    return render(request, 'main/login.html', {'error_message': error_message})


def logout_view(request):
    logout(request)
    return redirect('home')


@login_required
def profile_view(request):
    try:
        profile = request.user.profile
    except Profile.DoesNotExist:
        return redirect('home')

    total_minutes = LearningRecord.objects.filter(user=request.user).aggregate(
        total=Sum('minutes')
    )['total'] or 0

    purchased_count = Enrollment.objects.filter(student=request.user).count()

    return render(request, 'main/profile.html', {
        'profile': profile,
        'total_minutes': total_minutes,
        'purchased_count': purchased_count,
    })


@login_required
def student_dashboard(request):
    try:
        profile = request.user.profile
        if profile.role != 'student':
            return redirect('home')
    except Profile.DoesNotExist:
        return redirect('home')

    total_minutes = LearningRecord.objects.filter(user=request.user).aggregate(
        total=Sum('minutes')
    )['total'] or 0

    purchased_count = Enrollment.objects.filter(student=request.user).count()

    return render(request, 'main/student_dashboard.html', {
        'total_minutes': total_minutes,
        'purchased_count': purchased_count,
    })


@login_required
def teacher_dashboard(request):
    try:
        profile = request.user.profile
        if profile.role != 'teacher':
            return redirect('home')
    except Profile.DoesNotExist:
        return redirect('home')

    teacher_courses = Course.objects.filter(teacher=request.user)

    course_data = []
    for course in teacher_courses:
        purchase_count = Enrollment.objects.filter(course=course).count()
        total_watch_minutes = LearningRecord.objects.filter(course=course).aggregate(
            total=Sum('minutes')
        )['total'] or 0

        total_revenue = Order.objects.filter(
            course=course,
            status='paid'
        ).aggregate(total=Sum('final_price'))['total'] or 0

        course_data.append({
            'course': course,
            'purchase_count': purchase_count,
            'total_watch_minutes': total_watch_minutes,
            'total_revenue': total_revenue,
        })

    return render(request, 'main/teacher_dashboard.html', {
        'course_data': course_data
    })


@login_required
def my_courses(request):
    try:
        request.user.profile
    except Profile.DoesNotExist:
        return redirect('home')

    enrollments = Enrollment.objects.filter(
        student=request.user
    ).select_related('course')

    for enrollment in enrollments:
        enrollment.watch_minutes = LearningRecord.objects.filter(
            user=request.user,
            course=enrollment.course
        ).aggregate(total=Sum('minutes'))['total'] or 0

    total_minutes = LearningRecord.objects.filter(user=request.user).aggregate(
        total=Sum('minutes')
    )['total'] or 0

    return render(request, 'main/my_courses.html', {
        'enrollments': enrollments,
        'total_minutes': total_minutes,
    })


@login_required
def checkout(request, course_id):
    course = get_object_or_404(Course, id=course_id)

    try:
        request.user.profile
    except Profile.DoesNotExist:
        return redirect('home')

    if Enrollment.objects.filter(student=request.user, course=course).exists():
        return redirect('course_detail', course_id=course.id)

    form = CouponApplyForm(request.POST or None)

    original_price = course.price
    coupon = None
    discount_amount = 0
    final_price = original_price
    error_message = None
    success_message = None

    if request.method == 'POST':
        coupon_code = request.POST.get('coupon_code', '').strip()

        if coupon_code:
            try:
                coupon = Coupon.objects.get(code__iexact=coupon_code)
            except Coupon.DoesNotExist:
                coupon = None
                error_message = '找不到這張優惠券。'

            if coupon:
                if not coupon.is_valid_now():
                    error_message = '這張優惠券目前不可使用。'
                    coupon = None
                else:
                    discount_amount = coupon.calculate_discount(original_price)

                    if discount_amount <= 0:
                        error_message = '此優惠券未達最低消費金額或無法套用。'
                        coupon = None
                        discount_amount = 0
                    else:
                        final_price = original_price - discount_amount
                        success_message = f'優惠券已套用，折抵 NT$ {discount_amount}。'

        if not error_message:
            order = Order.objects.create(
                user=request.user,
                course=course,
                coupon=coupon,
                original_price=original_price,
                discount_amount=discount_amount,
                final_price=final_price,
                status='paid'
            )

            Enrollment.objects.get_or_create(
                student=request.user,
                course=course
            )

            if coupon:
                CouponUsage.objects.create(
                    user=request.user,
                    coupon=coupon,
                    order=order,
                    discount_amount=discount_amount
                )

            return redirect('order_success', order_id=order.id)

    return render(request, 'main/checkout.html', {
        'course': course,
        'form': form,
        'original_price': original_price,
        'discount_amount': discount_amount,
        'final_price': final_price,
        'error_message': error_message,
        'success_message': success_message,
    })


@login_required
def order_success(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    return render(request, 'main/order_success.html', {
        'order': order
    })


@login_required
def buy_course(request, course_id):
    return redirect('checkout', course_id=course_id)


@login_required
def purchase_success(request, course_id):
    course = get_object_or_404(Course, id=course_id)
    return render(request, 'main/purchase_success.html', {'course': course})


@login_required
def watch_course(request, course_id):
    course = get_object_or_404(Course, id=course_id)

    has_purchased = Enrollment.objects.filter(
        student=request.user,
        course=course
    ).exists()

    if not has_purchased:
        return redirect('course_detail', course_id=course.id)

    LearningRecord.objects.create(
        user=request.user,
        course=course,
        minutes=30
    )

    return redirect('my_courses')


@login_required
def create_course(request):
    try:
        profile = request.user.profile
        if profile.role != 'teacher':
            return redirect('home')
    except Profile.DoesNotExist:
        return redirect('home')

    if request.method == 'POST':
        form = CourseForm(request.POST, request.FILES)
        if form.is_valid():
            course = form.save(commit=False)
            course.teacher = request.user
            course.save()
            return redirect('teacher_dashboard')
    else:
        form = CourseForm()

    return render(request, 'main/create_course.html', {'form': form})


@login_required
def edit_course(request, course_id):
    try:
        profile = request.user.profile
        if profile.role != 'teacher':
            return redirect('home')
    except Profile.DoesNotExist:
        return redirect('home')

    course = get_object_or_404(Course, id=course_id, teacher=request.user)

    if request.method == 'POST':
        form = CourseForm(request.POST, request.FILES, instance=course)
        if form.is_valid():
            form.save()
            return redirect('teacher_dashboard')
    else:
        form = CourseForm(instance=course)

    return render(request, 'main/edit_course.html', {
        'form': form,
        'course': course
    })


@login_required
def delete_course(request, course_id):
    try:
        profile = request.user.profile
        if profile.role != 'teacher':
            return redirect('home')
    except Profile.DoesNotExist:
        return redirect('home')

    course = get_object_or_404(Course, id=course_id, teacher=request.user)

    if request.method == 'POST':
        course.delete()
        return redirect('teacher_dashboard')

    return render(request, 'main/delete_course.html', {
        'course': course
    })


@login_required
def export_data_page(request):
    if not request.user.is_superuser:
        return redirect('home')

    return render(request, 'main/export_data.html')


def create_csv_response(filename):
    response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    response.write('\ufeff')
    return response


@login_required
def export_courses_csv(request):
    if not request.user.is_superuser:
        return redirect('home')

    response = create_csv_response('courses.csv')
    writer = csv.writer(response)

    writer.writerow([
        'course_id',
        'course_title',
        'teacher_username',
        'teacher_email',
        'price',
        'description',
        'created_at',
    ])

    courses = Course.objects.select_related('teacher').all()

    for course in courses:
        writer.writerow([
            course.id,
            course.title,
            course.teacher.username,
            course.teacher.email,
            course.price,
            course.description,
            course.created_at,
        ])

    return response


@login_required
def export_enrollments_csv(request):
    if not request.user.is_superuser:
        return redirect('home')

    response = create_csv_response('enrollments.csv')
    writer = csv.writer(response)

    writer.writerow([
        'enrollment_id',
        'student_username',
        'student_email',
        'course_id',
        'course_title',
        'teacher_username',
        'purchased_at',
    ])

    enrollments = Enrollment.objects.select_related('student', 'course', 'course__teacher').all()

    for enrollment in enrollments:
        writer.writerow([
            enrollment.id,
            enrollment.student.username,
            enrollment.student.email,
            enrollment.course.id,
            enrollment.course.title,
            enrollment.course.teacher.username,
            enrollment.purchased_at,
        ])

    return response


@login_required
def export_learning_records_csv(request):
    if not request.user.is_superuser:
        return redirect('home')

    response = create_csv_response('learning_records.csv')
    writer = csv.writer(response)

    writer.writerow([
        'record_id',
        'username',
        'email',
        'course_id',
        'course_title',
        'teacher_username',
        'minutes',
        'watched_at',
    ])

    records = LearningRecord.objects.select_related('user', 'course', 'course__teacher').all()

    for record in records:
        writer.writerow([
            record.id,
            record.user.username,
            record.user.email,
            record.course.id,
            record.course.title,
            record.course.teacher.username,
            record.minutes,
            record.watched_at,
        ])

    return response


@login_required
def export_profiles_csv(request):
    if not request.user.is_superuser:
        return redirect('home')

    response = create_csv_response('profiles.csv')
    writer = csv.writer(response)

    writer.writerow([
        'profile_id',
        'username',
        'email',
        'role',
        'role_display',
    ])

    profiles = Profile.objects.select_related('user').all()

    for profile in profiles:
        writer.writerow([
            profile.id,
            profile.user.username,
            profile.user.email,
            profile.role,
            profile.get_role_display(),
        ])

    return response