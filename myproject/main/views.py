import csv
import json
from django.http import HttpResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Avg, Count, Q
from django.core.paginator import Paginator
from django.urls import reverse

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
    CourseChapter,
    CourseQuestion,
    CourseAnswer,
    CourseAudit,
    Promotion,
    CourseCategory,
)

from .forms import (
    RegisterForm,
    CourseForm,
    CouponApplyForm,
    ReviewForm,
    ChapterForm,
    LessonForm,
    QuestionForm,
    AnswerForm,
)


def home(request):
    sort = request.GET.get('sort', 'newest')
    q = request.GET.get('q', '').strip()
    cat = request.GET.get('cat', '').strip()

    qs = Course.objects.filter(is_published=True).select_related('teacher', 'category')

    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(teacher__username__icontains=q))
    if cat:
        qs = qs.filter(category__name=cat)

    qs = qs.annotate(student_count=Count('enrollment', distinct=True))

    sort_map = {
        'newest': '-created_at',
        'popular': '-student_count',
        'price_asc': 'price',
        'price_desc': '-price',
    }
    if sort not in sort_map:
        sort = 'newest'
    if sort == 'popular':
        qs = qs.order_by('-student_count', '-created_at')
    else:
        qs = qs.order_by(sort_map[sort])

    paginator = Paginator(qs, 6)
    page_obj = paginator.get_page(request.GET.get('page'))

    # 評分只計算本頁課程
    for c in page_obj:
        stats = Review.objects.filter(course=c).aggregate(avg=Avg('rating'), n=Count('id'))
        c.avg_rating = round(stats['avg'], 1) if stats['avg'] else None
        c.review_count = stats['n']

    categories = CourseCategory.objects.order_by('name')
    total_students = Enrollment.objects.values('student').distinct().count()
    total_courses = Course.objects.filter(is_published=True).count()

    return render(request, 'main/home.html', {
        'page_obj': page_obj,
        'sort': sort,
        'q': q,
        'cat': cat,
        'categories': categories,
        'total_students': total_students,
        'total_courses': total_courses,
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

    # A7：課程問答
    questions = CourseQuestion.objects.filter(
        course=course
    ).select_related('user').prefetch_related('answers__user').order_by('-created_at')

    is_course_teacher = request.user.is_authenticated and course.teacher_id == request.user.id

    # 課程統計（銷售頁用）
    total_lessons = CourseLesson.objects.filter(chapter__course=course).count()
    total_minutes = CourseLesson.objects.filter(chapter__course=course).aggregate(
        total=Sum('duration_minutes')
    )['total'] or 0
    student_count = Enrollment.objects.filter(course=course).count()

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
        'questions': questions,
        'question_form': QuestionForm(),
        'answer_form': AnswerForm(),
        'is_course_teacher': is_course_teacher,
        'total_lessons': total_lessons,
        'total_minutes': total_minutes,
        'student_count': student_count,
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

        course_total = CourseLesson.objects.filter(
            chapter__course=enrollment.course
        ).aggregate(total=Sum('duration_minutes'))['total'] or 0
        enrollment.course_total_minutes = course_total

        if course_total > 0:
            pct = int(min(enrollment.watch_minutes, course_total) / course_total * 100)
        else:
            pct = 0
        enrollment.progress = pct

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
    selected_code = ''

    if request.method == 'POST':
        # action：apply=只套用預覽折扣、buy=確認購買
        action = request.POST.get('action', 'buy')
        coupon_code = request.POST.get('coupon_code', '').strip()
        selected_code = coupon_code

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
        elif action == 'buy':
            success_message = None  # 沒輸入券，直接原價購買

        # 只有按「確認購買」且沒有錯誤時才真正成立訂單；
        # 按「套用優惠券」只重新整理頁面顯示折扣預覽。
        if action == 'buy' and not error_message:
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

                # A4：若這張券是使用者領取的，標記為已使用
                UserCoupon.objects.filter(
                    user=request.user,
                    coupon=coupon,
                    status='unused'
                ).update(status='used', used_at=timezone.now())

            Notification.objects.create(
                user=request.user,
                title='購買成功通知',
                content=f'你已成功購買「{course.title}」，實付金額 NT$ {final_price}。'
            )

            return redirect('order_success', order_id=order.id)

    # A4：帶出使用者可用的優惠券供選擇
    now = timezone.now()
    my_coupons = UserCoupon.objects.filter(
        user=request.user, status='unused'
    ).select_related('coupon').filter(
        coupon__is_active=True,
        coupon__start_date__lte=now,
        coupon__end_date__gte=now,
    )

    return render(request, 'main/checkout.html', {
        'course': course,
        'form': form,
        'original_price': original_price,
        'discount_amount': discount_amount,
        'final_price': final_price,
        'error_message': error_message,
        'success_message': success_message,
        'my_coupons': my_coupons,
        'selected_code': selected_code,
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

    if not has_purchased and course.teacher_id != request.user.id:
        return redirect('course_detail', course_id=course.id)

    # 導向課程第一個單元的播放頁
    first_lesson = CourseLesson.objects.filter(
        chapter__course=course
    ).order_by('chapter__sort_order', 'sort_order').first()

    if first_lesson:
        return redirect('watch_lesson', lesson_id=first_lesson.id)

    return redirect('course_detail', course_id=course.id)


@login_required
def watch_lesson(request, lesson_id):
    lesson = get_object_or_404(
        CourseLesson.objects.select_related('chapter__course'), id=lesson_id
    )
    course = lesson.chapter.course

    enrolled = Enrollment.objects.filter(student=request.user, course=course).exists()
    is_teacher = course.teacher_id == request.user.id

    # 免費試看單元任何登入者可看；其餘需購買或為講師
    if not (enrolled or is_teacher or lesson.is_free_preview):
        return redirect('course_detail', course_id=course.id)

    # 完成條件：影片播畢且實際觀看時長 ≥ 60%（防快轉刷課）
    if request.method == 'POST' and (enrolled or is_teacher):
        try:
            watched = float(request.POST.get('watched_seconds', 0))
            duration = float(request.POST.get('duration', 0))
        except (TypeError, ValueError):
            watched, duration = 0.0, 0.0

        ratio = (watched / duration) if duration > 0 else 0

        if ratio >= 0.6:
            LearningRecord.objects.get_or_create(
                user=request.user,
                course=course,
                lesson=lesson,
                defaults={'minutes': lesson.duration_minutes or 30}
            )
            return redirect('watch_lesson', lesson_id=lesson.id)

        # 未達 60% → 不記錄，帶錯誤旗標回頁面
        return redirect(f"{reverse('watch_lesson', args=[lesson.id])}?err=notenough")

    # 側欄：所有章節/單元 + 完成狀態
    chapters = course.chapters.prefetch_related('lessons').all()
    completed_ids = set(
        LearningRecord.objects.filter(user=request.user, course=course)
        .exclude(lesson=None).values_list('lesson_id', flat=True)
    )

    total_lessons = CourseLesson.objects.filter(chapter__course=course).count()
    done_count = len(completed_ids)
    progress = int(done_count / total_lessons * 100) if total_lessons else 0

    is_completed = lesson.id in completed_ids

    return render(request, 'main/watch_lesson.html', {
        'course': course,
        'lesson': lesson,
        'chapters': chapters,
        'completed_ids': completed_ids,
        'progress': progress,
        'done_count': done_count,
        'total_lessons': total_lessons,
        'is_completed': is_completed,
        'can_record': enrolled or is_teacher,
        'err': request.GET.get('err'),
    })


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
            course.is_published = False  # A8：送審前不上架
            course.save()

            CourseAudit.objects.create(course=course, status='pending')

            Notification.objects.create(
                user=request.user,
                title='課程已送審',
                content=f'你的課程「{course.title}」已送出審核，通過後才會上架。'
            )

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
    items = list(cart.items.select_related('course').all())
    now = timezone.now()

    # A5：有效促銷 → course_id 對應 Promotion
    promo_map = {}
    active_promos = Promotion.objects.filter(
        is_active=True, start_date__lte=now, end_date__gte=now
    ).prefetch_related('courses')
    for promo in active_promos:
        for c in promo.courses.all():
            promo_map.setdefault(c.id, promo)

    # A5：整車套用一張優惠券（依購物車總額計算，逐筆分攤）
    coupon = None
    if request.method == 'POST':
        code = request.POST.get('coupon_code', '').strip()
        if code:
            coupon = Coupon.objects.filter(code__iexact=code).first()
            if coupon and not coupon.is_valid_now():
                coupon = None

    cart_total = sum(i.course.price for i in items)
    coupon_remaining = coupon.calculate_discount(cart_total) if coupon else 0
    coupon_used_total = 0

    for item in items:
        course = item.course
        if Enrollment.objects.filter(student=request.user, course=course).exists():
            continue

        original = course.price
        discount = 0

        # 促銷折扣
        promo = promo_map.get(course.id)
        if promo:
            if promo.discount_type == 'amount':
                discount += min(promo.discount_value, original)
            else:
                discount += int(original * promo.discount_value / 100)

        price_after_promo = original - discount

        # 優惠券分攤
        coupon_here = 0
        if coupon_remaining > 0 and price_after_promo > 0:
            coupon_here = min(coupon_remaining, price_after_promo)
            discount += coupon_here
            coupon_remaining -= coupon_here
            coupon_used_total += coupon_here

        final_price = original - discount

        order = Order.objects.create(
            user=request.user,
            course=course,
            coupon=coupon if coupon_here > 0 else None,
            original_price=original,
            discount_amount=discount,
            final_price=final_price,
            status='paid'
        )
        OrderItem.objects.create(order=order, course=course, price=original)
        Payment.objects.create(
            order=order,
            method='mock',
            amount=final_price,
            status='paid',
            transaction_no=f'MOCK-{order.id:05d}',
            paid_at=order.created_at
        )
        Enrollment.objects.get_or_create(student=request.user, course=course)
        Notification.objects.create(
            user=request.user,
            title='購買成功通知',
            content=f'你已成功購買「{course.title}」，實付金額 NT$ {final_price}。'
        )
        if coupon_here > 0:
            CouponUsage.objects.create(
                user=request.user, coupon=coupon, order=order, discount_amount=coupon_here
            )

    # 券有實際使用才標記為已用
    if coupon and coupon_used_total > 0:
        UserCoupon.objects.filter(
            user=request.user, coupon=coupon, status='unused'
        ).update(status='used', used_at=now)

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


# =========================
# A2 章節 / 單元管理（老師）
# =========================

def _require_course_teacher(request, course_id):
    """回傳 (course, None) 或 (None, redirect)。只有課程講師本人可管理。"""
    try:
        profile = request.user.profile
    except Profile.DoesNotExist:
        return None, redirect('home')

    if profile.role != 'teacher':
        return None, redirect('home')

    course = get_object_or_404(Course, id=course_id, teacher=request.user)
    return course, None


@login_required
def manage_content(request, course_id):
    course, redirect_resp = _require_course_teacher(request, course_id)
    if redirect_resp:
        return redirect_resp

    chapters = course.chapters.prefetch_related('lessons').all()

    return render(request, 'main/manage_content.html', {
        'course': course,
        'chapters': chapters,
        'chapter_form': ChapterForm(),
        'lesson_form': LessonForm(),
    })


@login_required
def add_chapter(request, course_id):
    course, redirect_resp = _require_course_teacher(request, course_id)
    if redirect_resp:
        return redirect_resp

    if request.method == 'POST':
        form = ChapterForm(request.POST)
        if form.is_valid():
            chapter = form.save(commit=False)
            chapter.course = course
            chapter.save()

    return redirect('manage_content', course_id=course.id)


@login_required
def edit_chapter(request, chapter_id):
    chapter = get_object_or_404(CourseChapter, id=chapter_id)
    course, redirect_resp = _require_course_teacher(request, chapter.course_id)
    if redirect_resp:
        return redirect_resp

    if request.method == 'POST':
        form = ChapterForm(request.POST, instance=chapter)
        if form.is_valid():
            form.save()
            return redirect('manage_content', course_id=course.id)
    else:
        form = ChapterForm(instance=chapter)

    return render(request, 'main/edit_chapter.html', {
        'form': form,
        'chapter': chapter,
        'course': course,
    })


@login_required
def delete_chapter(request, chapter_id):
    chapter = get_object_or_404(CourseChapter, id=chapter_id)
    course, redirect_resp = _require_course_teacher(request, chapter.course_id)
    if redirect_resp:
        return redirect_resp

    if request.method == 'POST':
        chapter.delete()

    return redirect('manage_content', course_id=course.id)


@login_required
def add_lesson(request, chapter_id):
    chapter = get_object_or_404(CourseChapter, id=chapter_id)
    course, redirect_resp = _require_course_teacher(request, chapter.course_id)
    if redirect_resp:
        return redirect_resp

    if request.method == 'POST':
        form = LessonForm(request.POST, request.FILES)
        if form.is_valid():
            lesson = form.save(commit=False)
            lesson.chapter = chapter
            lesson.save()

    return redirect('manage_content', course_id=course.id)


@login_required
def edit_lesson(request, lesson_id):
    lesson = get_object_or_404(CourseLesson, id=lesson_id)
    course, redirect_resp = _require_course_teacher(request, lesson.chapter.course_id)
    if redirect_resp:
        return redirect_resp

    if request.method == 'POST':
        form = LessonForm(request.POST, request.FILES, instance=lesson)
        if form.is_valid():
            form.save()
            return redirect('manage_content', course_id=course.id)
    else:
        form = LessonForm(instance=lesson)

    return render(request, 'main/edit_lesson.html', {
        'form': form,
        'lesson': lesson,
        'course': course,
    })


@login_required
def delete_lesson(request, lesson_id):
    lesson = get_object_or_404(CourseLesson, id=lesson_id)
    course, redirect_resp = _require_course_teacher(request, lesson.chapter.course_id)
    if redirect_resp:
        return redirect_resp

    if request.method == 'POST':
        lesson.delete()

    return redirect('manage_content', course_id=course.id)


# =========================
# A3 退款審核（老師 / 管理員）
# =========================

@login_required
def manage_refunds(request):
    if request.user.is_superuser:
        refunds = Refund.objects.select_related(
            'order', 'order__course', 'user'
        ).order_by('-created_at')
    else:
        try:
            profile = request.user.profile
        except Profile.DoesNotExist:
            return redirect('home')
        if profile.role != 'teacher':
            return redirect('home')
        refunds = Refund.objects.filter(
            order__course__teacher=request.user
        ).select_related('order', 'order__course', 'user').order_by('-created_at')

    return render(request, 'main/manage_refunds.html', {
        'refunds': refunds,
    })


@login_required
def process_refund(request, refund_id):
    refund = get_object_or_404(Refund, id=refund_id)

    # 權限：管理員或該課程講師
    is_teacher = (
        not request.user.is_superuser
        and refund.order.course
        and refund.order.course.teacher_id == request.user.id
    )
    if not (request.user.is_superuser or is_teacher):
        return redirect('home')

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'approve' and refund.status == 'pending':
            refund.status = 'approved'
            refund.processed_at = timezone.now()
            refund.save()
            order = refund.order
            order.status = 'refunded'
            order.save()
            Notification.objects.create(
                user=refund.user,
                title='退款已通過',
                content=f'訂單 #{order.id} 的退款申請已通過，將退還 NT$ {refund.amount}。'
            )
        elif action == 'reject' and refund.status == 'pending':
            refund.status = 'rejected'
            refund.processed_at = timezone.now()
            refund.save()
            Notification.objects.create(
                user=refund.user,
                title='退款未通過',
                content=f'訂單 #{refund.order.id} 的退款申請未通過。'
            )

    return redirect('manage_refunds')


# =========================
# A6 通知中心
# =========================

@login_required
def notifications(request):
    notes = Notification.objects.filter(
        user=request.user
    ).order_by('-created_at')

    return render(request, 'main/notifications.html', {
        'notifications': notes,
    })


@login_required
def mark_notifications_read(request):
    if request.method == 'POST':
        Notification.objects.filter(
            user=request.user, is_read=False
        ).update(is_read=True)
    return redirect('notifications')


# =========================
# A7 課程問答
# =========================

@login_required
def add_question(request, course_id):
    course = get_object_or_404(Course, id=course_id)

    purchased = Enrollment.objects.filter(
        student=request.user, course=course
    ).exists()
    is_teacher = course.teacher_id == request.user.id

    if request.method == 'POST' and (purchased or is_teacher):
        form = QuestionForm(request.POST)
        if form.is_valid():
            q = form.save(commit=False)
            q.user = request.user
            q.course = course
            q.save()
            if not is_teacher:
                Notification.objects.create(
                    user=course.teacher,
                    title='課程有新提問',
                    content=f'課程「{course.title}」收到新的問題：{q.title}'
                )

    return redirect('course_detail', course_id=course.id)


@login_required
def add_answer(request, question_id):
    question = get_object_or_404(CourseQuestion, id=question_id)
    course = question.course

    is_teacher = course.teacher_id == request.user.id
    if not (is_teacher or request.user.is_superuser):
        return redirect('course_detail', course_id=course.id)

    if request.method == 'POST':
        form = AnswerForm(request.POST)
        if form.is_valid():
            a = form.save(commit=False)
            a.question = question
            a.user = request.user
            a.save()
            Notification.objects.create(
                user=question.user,
                title='你的提問已被回覆',
                content=f'課程「{course.title}」中你的問題「{question.title}」已有回答。'
            )

    return redirect('course_detail', course_id=course.id)


# =========================
# A8 課程審核（管理員）
# =========================

@login_required
def manage_audits(request):
    if not request.user.is_superuser:
        return redirect('home')

    audits = CourseAudit.objects.select_related(
        'course', 'course__teacher', 'reviewer'
    ).order_by('-created_at')

    return render(request, 'main/manage_audits.html', {
        'audits': audits,
    })


@login_required
def process_audit(request, audit_id):
    if not request.user.is_superuser:
        return redirect('home')

    audit = get_object_or_404(CourseAudit, id=audit_id)

    if request.method == 'POST':
        action = request.POST.get('action')
        comment = request.POST.get('comment', '').strip()

        if action == 'approve':
            audit.status = 'approved'
            audit.reviewer = request.user
            audit.comment = comment
            audit.reviewed_at = timezone.now()
            audit.save()
            course = audit.course
            course.is_published = True
            course.save()
            Notification.objects.create(
                user=course.teacher,
                title='課程審核通過',
                content=f'你的課程「{course.title}」已通過審核並上架。'
            )
        elif action == 'reject':
            audit.status = 'rejected'
            audit.reviewer = request.user
            audit.comment = comment
            audit.reviewed_at = timezone.now()
            audit.save()
            course = audit.course
            course.is_published = False
            course.save()
            Notification.objects.create(
                user=course.teacher,
                title='課程審核未通過',
                content=f'你的課程「{course.title}」未通過審核。原因：{comment or "未提供"}'
            )

    return redirect('manage_audits')

# =========================
# Task 2 課程完成證書（PDF）
# =========================

def _course_completion(user, course):
    """回傳 (total_lessons, done_count, is_complete)。"""
    total = CourseLesson.objects.filter(chapter__course=course).count()
    done = LearningRecord.objects.filter(
        user=user, course=course
    ).exclude(lesson=None).values('lesson').distinct().count()
    is_complete = total > 0 and done >= total
    return total, done, is_complete


@login_required
def certificate(request, course_id):
    course = get_object_or_404(Course, id=course_id)

    if not Enrollment.objects.filter(student=request.user, course=course).exists():
        return redirect('course_detail', course_id=course.id)

    total, done, is_complete = _course_completion(request.user, course)
    if not is_complete:
        return redirect('my_courses')

    import io
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont

    # 繁體中文內建 CID 字型（免安裝字型檔）
    pdfmetrics.registerFont(UnicodeCIDFont('MSung-Light'))
    FONT = 'MSung-Light'

    buffer = io.BytesIO()
    W, H = landscape(A4)
    c = canvas.Canvas(buffer, pagesize=landscape(A4))

    # 背景與外框
    c.setFillColorRGB(0.97, 0.97, 1.0)
    c.rect(0, 0, W, H, fill=1, stroke=0)
    c.setStrokeColorRGB(0.31, 0.27, 0.90)
    c.setLineWidth(4)
    c.rect(15 * mm, 15 * mm, W - 30 * mm, H - 30 * mm, fill=0, stroke=1)
    c.setStrokeColorRGB(0.49, 0.36, 0.93)
    c.setLineWidth(1)
    c.rect(19 * mm, 19 * mm, W - 38 * mm, H - 38 * mm, fill=0, stroke=1)

    cx = W / 2

    c.setFillColorRGB(0.31, 0.27, 0.90)
    c.setFont(FONT, 40)
    c.drawCentredString(cx, H - 55 * mm, '結業證書')

    c.setFillColorRGB(0.42, 0.45, 0.5)
    c.setFont('Helvetica', 14)
    c.drawCentredString(cx, H - 66 * mm, 'CERTIFICATE OF COMPLETION')

    c.setFillColorRGB(0.2, 0.2, 0.25)
    c.setFont(FONT, 15)
    c.drawCentredString(cx, H - 90 * mm, '茲證明')

    c.setFillColorRGB(0.1, 0.1, 0.15)
    c.setFont(FONT, 30)
    c.drawCentredString(cx, H - 108 * mm, request.user.username)

    c.setStrokeColorRGB(0.7, 0.7, 0.75)
    c.setLineWidth(0.8)
    c.line(cx - 70 * mm, H - 112 * mm, cx + 70 * mm, H - 112 * mm)

    c.setFillColorRGB(0.2, 0.2, 0.25)
    c.setFont(FONT, 15)
    c.drawCentredString(cx, H - 126 * mm, '已完成本平台線上課程')

    c.setFillColorRGB(0.31, 0.27, 0.90)
    c.setFont(FONT, 22)
    c.drawCentredString(cx, H - 142 * mm, course.title)

    c.setFillColorRGB(0.3, 0.3, 0.35)
    c.setFont(FONT, 13)
    c.drawCentredString(cx, H - 158 * mm, f'授課講師：{course.teacher.username}　　完成日期：{timezone.now():%Y-%m-%d}')

    c.setFillColorRGB(0.55, 0.55, 0.6)
    c.setFont('Helvetica', 10)
    c.drawCentredString(cx, 26 * mm, f'Course Platform　|　證書編號 CERT-{course.id:04d}-{request.user.id:04d}')

    c.showPage()
    c.save()
    buffer.seek(0)

    response = HttpResponse(buffer, content_type='application/pdf')
    filename = f'certificate_{course.id}_{request.user.id}.pdf'
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


# =========================
# Task 4 講師公開頁
# =========================

def teacher_profile(request, teacher_id):
    teacher = get_object_or_404(User, id=teacher_id)

    courses = list(
        Course.objects.filter(teacher=teacher, is_published=True)
        .select_related('category')
        .annotate(student_count=Count('enrollment', distinct=True))
        .order_by('-created_at')
    )
    for c in courses:
        stats = Review.objects.filter(course=c).aggregate(avg=Avg('rating'), n=Count('id'))
        c.avg_rating = round(stats['avg'], 1) if stats['avg'] else None
        c.review_count = stats['n']

    total_students = Enrollment.objects.filter(
        course__teacher=teacher
    ).values('student').distinct().count()

    avg = Review.objects.filter(course__teacher=teacher).aggregate(a=Avg('rating'))['a']
    avg_rating = round(avg, 1) if avg else None
    review_count = Review.objects.filter(course__teacher=teacher).count()

    recent_reviews = Review.objects.filter(
        course__teacher=teacher
    ).select_related('user', 'course').order_by('-created_at')[:6]

    try:
        role_display = teacher.profile.get_role_display()
    except Profile.DoesNotExist:
        role_display = ''

    return render(request, 'main/teacher_profile.html', {
        'teacher': teacher,
        'role_display': role_display,
        'courses': courses,
        'course_count': len(courses),
        'total_students': total_students,
        'avg_rating': avg_rating,
        'review_count': review_count,
        'recent_reviews': recent_reviews,
    })
