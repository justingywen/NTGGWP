import csv
import json
from django.http import HttpResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Avg

from django.utils import timezone

from .models import (
    Course,
    CourseLesson,
    Profile,
    Enrollment,
    LearningRecord,
    Coupon,
    Order,
    OrderItem,
    CouponUsage,
    Payment,
    Notification,
    Review,
    Cart,
    CartItem,
    Favorite,
    Refund,
    UserCoupon,
)

from .forms import RegisterForm, CourseForm, CouponApplyForm, ReviewForm


def home(request):
    courses = Course.objects.filter(is_published=True).select_related(
        'teacher',
        'category'
    )

    return render(request, 'main/home.html', {
        'courses': courses
    })


def course_detail(request, course_id):
    course = get_object_or_404(Course, id=course_id)

    already_purchased = False
    can_review = False
    my_review = None
    review_form = None
    is_favorited = False

    if request.user.is_authenticated:
        already_purchased = Enrollment.objects.filter(
            student=request.user,
            course=course
        ).exists()

        is_favorited = Favorite.objects.filter(
            user=request.user,
            course=course
        ).exists()

        if already_purchased:
            can_review = True
            my_review = Review.objects.filter(
                user=request.user,
                course=course
            ).first()

    if request.method == 'POST':
        if not request.user.is_authenticated:
            return redirect('login')

        if not already_purchased:
            return redirect('course_detail', course_id=course.id)

        if my_review:
            review_form = ReviewForm(request.POST, instance=my_review)
        else:
            review_form = ReviewForm(request.POST)

        if review_form.is_valid():
            review = review_form.save(commit=False)
            review.user = request.user
            review.course = course
            review.save()

            return redirect('course_detail', course_id=course.id)

    else:
        if my_review:
            review_form = ReviewForm(instance=my_review)
        else:
            review_form = ReviewForm()

    chapters = course.chapters.prefetch_related('lessons').all()

    reviews = Review.objects.filter(
        course=course
    ).select_related('user').order_by('-created_at')

    average_rating = reviews.aggregate(avg=Avg('rating'))['avg']
    if average_rating:
        average_rating = round(average_rating, 1)

    review_count = reviews.count()

    return render(request, 'main/course_detail.html', {
        'course': course,
        'already_purchased': already_purchased,
        'chapters': chapters,
        'reviews': reviews,
        'average_rating': average_rating,
        'review_count': review_count,
        'can_review': can_review,
        'my_review': my_review,
        'review_form': review_form,
        'is_favorited': is_favorited,
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

    return render(request, 'main/register.html', {
        'form': form
    })


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

        user = authenticate(
            request,
            username=username,
            password=password
        )

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

    return render(request, 'main/login.html', {
        'error_message': error_message
    })


def logout_view(request):
    logout(request)
    return redirect('home')


@login_required
def profile_view(request):
    try:
        profile = request.user.profile
    except Profile.DoesNotExist:
        return redirect('home')

    total_minutes = LearningRecord.objects.filter(
        user=request.user
    ).aggregate(
        total=Sum('minutes')
    )['total'] or 0

    purchased_count = Enrollment.objects.filter(
        student=request.user
    ).count()

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

    total_minutes = LearningRecord.objects.filter(
        user=request.user
    ).aggregate(
        total=Sum('minutes')
    )['total'] or 0

    purchased_count = Enrollment.objects.filter(
        student=request.user
    ).count()

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

    teacher_courses = Course.objects.filter(
        teacher=request.user
    ).select_related('category')

    course_data = []

    for course in teacher_courses:
        purchase_count = Enrollment.objects.filter(
            course=course
        ).count()

        total_watch_minutes = LearningRecord.objects.filter(
            course=course
        ).aggregate(
            total=Sum('minutes')
        )['total'] or 0

        total_revenue = Order.objects.filter(
            course=course,
            status='paid'
        ).aggregate(
            total=Sum('final_price')
        )['total'] or 0

        average_rating = Review.objects.filter(
            course=course
        ).aggregate(
            avg=Avg('rating')
        )['avg']

        if average_rating:
            average_rating = round(average_rating, 1)

        course_data.append({
            'course': course,
            'purchase_count': purchase_count,
            'total_watch_minutes': total_watch_minutes,
            'total_revenue': total_revenue,
            'average_rating': average_rating,
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
    ).select_related('course', 'course__teacher', 'course__category')

    for enrollment in enrollments:
        enrollment.watch_minutes = LearningRecord.objects.filter(
            user=request.user,
            course=enrollment.course
        ).aggregate(
            total=Sum('minutes')
        )['total'] or 0

    total_minutes = LearningRecord.objects.filter(
        user=request.user
    ).aggregate(
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

    if Enrollment.objects.filter(
        student=request.user,
        course=course
    ).exists():
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

            OrderItem.objects.create(
                order=order,
                course=course,
                price=original_price
            )

            Payment.objects.create(
                order=order,
                method='mock',
                amount=final_price,
                status='paid',
                transaction_no=f'MOCK-{order.id:05d}',
                paid_at=order.created_at
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

            Notification.objects.create(
                user=request.user,
                title='購買成功通知',
                content=f'你已成功購買「{course.title}」，實付金額 NT$ {final_price}。'
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
    order = get_object_or_404(
        Order,
        id=order_id,
        user=request.user
    )

    return render(request, 'main/order_success.html', {
        'order': order
    })


@login_required
def buy_course(request, course_id):
    return redirect('checkout', course_id=course_id)


@login_required
def purchase_success(request, course_id):
    course = get_object_or_404(Course, id=course_id)

    return render(request, 'main/purchase_success.html', {
        'course': course
    })


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

    return render(request, 'main/create_course.html', {
        'form': form
    })


@login_required
def edit_course(request, course_id):
    try:
        profile = request.user.profile

        if profile.role != 'teacher':
            return redirect('home')

    except Profile.DoesNotExist:
        return redirect('home')

    course = get_object_or_404(
        Course,
        id=course_id,
        teacher=request.user
    )

    if request.method == 'POST':
        form = CourseForm(
            request.POST,
            request.FILES,
            instance=course
        )

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

    course = get_object_or_404(
        Course,
        id=course_id,
        teacher=request.user
    )

    if request.method == 'POST':
        course.delete()
        return redirect('teacher_dashboard')

    return render(request, 'main/delete_course.html', {
        'course': course
    })


@login_required
def student_analytics(request):
    try:
        profile = request.user.profile
        if profile.role != 'student':
            return redirect('home')
    except Profile.DoesNotExist:
        return redirect('home')

    total_minutes = LearningRecord.objects.filter(
        user=request.user
    ).aggregate(
        total=Sum('minutes')
    )['total'] or 0

    purchased_count = Enrollment.objects.filter(
        student=request.user
    ).count()

    course_minutes_data = LearningRecord.objects.filter(
        user=request.user
    ).values(
        'course__title'
    ).annotate(
        total=Sum('minutes')
    ).order_by('-total')

    course_labels = [item['course__title'] for item in course_minutes_data]
    course_minutes = [item['total'] for item in course_minutes_data]

    recent_records = LearningRecord.objects.filter(
        user=request.user
    ).select_related(
        'course',
        'lesson'
    ).order_by('-watched_at')[:10]

    return render(request, 'main/student_analytics.html', {
        'total_minutes': total_minutes,
        'purchased_count': purchased_count,
        'course_labels_json': json.dumps(course_labels, ensure_ascii=False),
        'course_minutes_json': json.dumps(course_minutes),
        'recent_records': recent_records,
    })


@login_required
def teacher_analytics(request):
    try:
        profile = request.user.profile
        if profile.role != 'teacher':
            return redirect('home')
    except Profile.DoesNotExist:
        return redirect('home')

    teacher_courses = Course.objects.filter(
        teacher=request.user
    )

    total_revenue = Order.objects.filter(
        course__teacher=request.user,
        status='paid'
    ).aggregate(
        total=Sum('final_price')
    )['total'] or 0

    total_purchase_count = Enrollment.objects.filter(
        course__teacher=request.user
    ).count()

    total_watch_minutes = LearningRecord.objects.filter(
        course__teacher=request.user
    ).aggregate(
        total=Sum('minutes')
    )['total'] or 0

    course_labels = []
    purchase_counts = []
    revenue_data = []
    watch_minutes_data = []
    rating_data = []

    for course in teacher_courses:
        purchase_count = Enrollment.objects.filter(course=course).count()

        revenue = Order.objects.filter(
            course=course,
            status='paid'
        ).aggregate(
            total=Sum('final_price')
        )['total'] or 0

        watch_minutes = LearningRecord.objects.filter(
            course=course
        ).aggregate(
            total=Sum('minutes')
        )['total'] or 0

        avg_rating = Review.objects.filter(
            course=course
        ).aggregate(
            avg=Avg('rating')
        )['avg'] or 0

        course_labels.append(course.title)
        purchase_counts.append(purchase_count)
        revenue_data.append(revenue)
        watch_minutes_data.append(watch_minutes)
        rating_data.append(round(avg_rating, 1))

    return render(request, 'main/teacher_analytics.html', {
        'total_revenue': total_revenue,
        'total_purchase_count': total_purchase_count,
        'total_watch_minutes': total_watch_minutes,
        'course_labels_json': json.dumps(course_labels, ensure_ascii=False),
        'purchase_counts_json': json.dumps(purchase_counts),
        'revenue_data_json': json.dumps(revenue_data),
        'watch_minutes_data_json': json.dumps(watch_minutes_data),
        'rating_data_json': json.dumps(rating_data),
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
        'category',
        'level',
        'price',
        'description',
        'is_published',
        'created_at',
    ])

    courses = Course.objects.select_related(
        'teacher',
        'category'
    ).all()

    for course in courses:
        writer.writerow([
            course.id,
            course.title,
            course.teacher.username,
            course.teacher.email,
            course.category.name if course.category else '',
            course.get_level_display(),
            course.price,
            course.description,
            course.is_published,
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

    enrollments = Enrollment.objects.select_related(
        'student',
        'course',
        'course__teacher'
    ).all()

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
        'lesson_title',
        'minutes',
        'watched_at',
    ])

    records = LearningRecord.objects.select_related(
        'user',
        'course',
        'course__teacher',
        'lesson'
    ).all()

    for record in records:
        writer.writerow([
            record.id,
            record.user.username,
            record.user.email,
            record.course.id,
            record.course.title,
            record.course.teacher.username,
            record.lesson.title if record.lesson else '',
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

@login_required
def export_orders_csv(request):
    if not request.user.is_superuser:
        return redirect('home')

    response = create_csv_response('orders.csv')
    writer = csv.writer(response)

    writer.writerow([
        'order_id',
        'username',
        'email',
        'course_id',
        'course_title',
        'coupon_code',
        'original_price',
        'discount_amount',
        'final_price',
        'status',
        'created_at',
    ])

    orders = Order.objects.select_related(
        'user',
        'course',
        'coupon'
    ).all()

    for order in orders:
        writer.writerow([
            order.id,
            order.user.username,
            order.user.email,
            order.course.id if order.course else '',
            order.course.title if order.course else '',
            order.coupon.code if order.coupon else '',
            order.original_price,
            order.discount_amount,
            order.final_price,
            order.status,
            order.created_at,
        ])

    return response


@login_required
def export_order_items_csv(request):
    if not request.user.is_superuser:
        return redirect('home')

    response = create_csv_response('order_items.csv')
    writer = csv.writer(response)

    writer.writerow([
        'order_item_id',
        'order_id',
        'username',
        'course_id',
        'course_title',
        'teacher_username',
        'price',
    ])

    items = OrderItem.objects.select_related(
        'order',
        'order__user',
        'course',
        'course__teacher'
    ).all()

    for item in items:
        writer.writerow([
            item.id,
            item.order.id,
            item.order.user.username,
            item.course.id,
            item.course.title,
            item.course.teacher.username,
            item.price,
        ])

    return response


@login_required
def export_payments_csv(request):
    if not request.user.is_superuser:
        return redirect('home')

    response = create_csv_response('payments.csv')
    writer = csv.writer(response)

    writer.writerow([
        'payment_id',
        'order_id',
        'username',
        'method',
        'amount',
        'status',
        'transaction_no',
        'paid_at',
        'created_at',
    ])

    payments = Payment.objects.select_related(
        'order',
        'order__user'
    ).all()

    for payment in payments:
        writer.writerow([
            payment.id,
            payment.order.id,
            payment.order.user.username,
            payment.method,
            payment.amount,
            payment.status,
            payment.transaction_no,
            payment.paid_at,
            payment.created_at,
        ])

    return response


@login_required
def export_coupon_usage_csv(request):
    if not request.user.is_superuser:
        return redirect('home')

    response = create_csv_response('coupon_usage.csv')
    writer = csv.writer(response)

    writer.writerow([
        'coupon_usage_id',
        'username',
        'coupon_code',
        'coupon_name',
        'order_id',
        'discount_amount',
        'used_at',
    ])

    usages = CouponUsage.objects.select_related(
        'user',
        'coupon',
        'order'
    ).all()

    for usage in usages:
        writer.writerow([
            usage.id,
            usage.user.username,
            usage.coupon.code,
            usage.coupon.name,
            usage.order.id,
            usage.discount_amount,
            usage.used_at,
        ])

    return response


@login_required
def export_reviews_csv(request):
    if not request.user.is_superuser:
        return redirect('home')

    response = create_csv_response('reviews.csv')
    writer = csv.writer(response)

    writer.writerow([
        'review_id',
        'username',
        'email',
        'course_id',
        'course_title',
        'teacher_username',
        'rating',
        'comment',
        'created_at',
        'updated_at',
    ])

    reviews = Review.objects.select_related(
        'user',
        'course',
        'course__teacher'
    ).all()

    for review in reviews:
        writer.writerow([
            review.id,
            review.user.username,
            review.user.email,
            review.course.id,
            review.course.title,
            review.course.teacher.username,
            review.rating,
            review.comment,
            review.created_at,
            review.updated_at,
        ])

    return response


@login_required
def export_course_lessons_csv(request):
    if not request.user.is_superuser:
        return redirect('home')

    response = create_csv_response('course_lessons.csv')
    writer = csv.writer(response)

    writer.writerow([
        'lesson_id',
        'course_id',
        'course_title',
        'chapter_id',
        'chapter_title',
        'lesson_title',
        'duration_minutes',
        'is_free_preview',
        'sort_order',
        'created_at',
    ])

    lessons = CourseLesson.objects.select_related(
        'chapter',
        'chapter__course'
    ).all()

    for lesson in lessons:
        writer.writerow([
            lesson.id,
            lesson.chapter.course.id,
            lesson.chapter.course.title,
            lesson.chapter.id,
            lesson.chapter.title,
            lesson.title,
            lesson.duration_minutes,
            lesson.is_free_preview,
            lesson.sort_order,
            lesson.created_at,
        ])

    return response


# =========================
# 購物車 Cart
# =========================

@login_required
def add_to_cart(request, course_id):
    course = get_object_or_404(Course, id=course_id)

    if Enrollment.objects.filter(student=request.user, course=course).exists():
        return redirect('course_detail', course_id=course.id)

    cart, _ = Cart.objects.get_or_create(user=request.user)
    CartItem.objects.get_or_create(cart=cart, course=course)

    return redirect('view_cart')


@login_required
def view_cart(request):
    cart, _ = Cart.objects.get_or_create(user=request.user)
    items = cart.items.select_related('course', 'course__teacher').all()
    total = sum(item.course.price for item in items)

    return render(request, 'main/cart.html', {
        'items': items,
        'total': total,
    })


@login_required
def remove_from_cart(request, item_id):
    item = get_object_or_404(CartItem, id=item_id, cart__user=request.user)
    item.delete()
    return redirect('view_cart')


@login_required
def cart_checkout(request):
    cart, _ = Cart.objects.get_or_create(user=request.user)
    items = cart.items.select_related('course').all()

    created_count = 0

    for item in items:
        course = item.course

        if Enrollment.objects.filter(student=request.user, course=course).exists():
            continue

        order = Order.objects.create(
            user=request.user,
            course=course,
            original_price=course.price,
            discount_amount=0,
            final_price=course.price,
            status='paid'
        )
        OrderItem.objects.create(order=order, course=course, price=course.price)
        Payment.objects.create(
            order=order,
            method='mock',
            amount=course.price,
            status='paid',
            transaction_no=f'MOCK-{order.id:05d}',
            paid_at=order.created_at
        )
        Enrollment.objects.get_or_create(student=request.user, course=course)
        Notification.objects.create(
            user=request.user,
            title='購買成功通知',
            content=f'你已成功購買「{course.title}」，實付金額 NT$ {course.price}。'
        )
        created_count += 1

    cart.items.all().delete()

    return redirect('my_courses')


# =========================
# 收藏 Favorite
# =========================

@login_required
def toggle_favorite(request, course_id):
    course = get_object_or_404(Course, id=course_id)
    favorite = Favorite.objects.filter(user=request.user, course=course).first()

    if favorite:
        favorite.delete()
    else:
        Favorite.objects.create(user=request.user, course=course)

    next_url = request.POST.get('next') or request.GET.get('next')
    if next_url:
        return redirect(next_url)
    return redirect('my_favorites')


@login_required
def my_favorites(request):
    favorites = Favorite.objects.filter(
        user=request.user
    ).select_related('course', 'course__teacher', 'course__category').order_by('-created_at')

    return render(request, 'main/favorites.html', {
        'favorites': favorites,
    })


# =========================
# 退款 Refund
# =========================

@login_required
def request_refund(request, order_id):
    order = get_object_or_404(
        Order, id=order_id, user=request.user, status='paid'
    )

    existing = Refund.objects.filter(
        order=order, status__in=['pending', 'approved']
    ).first()

    if request.method == 'POST' and not existing:
        reason = request.POST.get('reason', '').strip() or '未填寫原因'
        Refund.objects.create(
            order=order,
            user=request.user,
            amount=order.final_price,
            reason=reason,
            status='pending'
        )
        Notification.objects.create(
            user=request.user,
            title='退款申請已送出',
            content=f'訂單 #{order.id} 的退款申請已送出，等待審核。'
        )
        return redirect('my_refunds')

    return render(request, 'main/request_refund.html', {
        'order': order,
        'existing': existing,
    })


@login_required
def my_refunds(request):
    refunds = Refund.objects.filter(
        user=request.user
    ).select_related('order', 'order__course').order_by('-created_at')

    orders = Order.objects.filter(
        user=request.user, status='paid'
    ).select_related('course').order_by('-created_at')

    return render(request, 'main/refunds.html', {
        'refunds': refunds,
        'orders': orders,
    })


# =========================
# 優惠券領取 UserCoupon
# =========================

@login_required
def coupon_list(request):
    now = timezone.now()
    coupons = Coupon.objects.filter(
        is_active=True, start_date__lte=now, end_date__gte=now
    ).order_by('-created_at')

    claimed_ids = set(
        UserCoupon.objects.filter(user=request.user).values_list('coupon_id', flat=True)
    )

    return render(request, 'main/coupons.html', {
        'coupons': coupons,
        'claimed_ids': claimed_ids,
    })


@login_required
def claim_coupon(request, coupon_id):
    coupon = get_object_or_404(Coupon, id=coupon_id)

    if coupon.is_valid_now():
        UserCoupon.objects.get_or_create(
            user=request.user,
            coupon=coupon,
            defaults={'status': 'unused'}
        )

    return redirect('my_coupons')


@login_required
def my_coupons(request):
    user_coupons = UserCoupon.objects.filter(
        user=request.user
    ).select_related('coupon').order_by('-received_at')

    return render(request, 'main/my_coupons.html', {
        'user_coupons': user_coupons,
    })