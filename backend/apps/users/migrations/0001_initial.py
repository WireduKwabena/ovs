import uuid

import django.contrib.auth.models
import django.core.validators
import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        migrations.CreateModel(
            name='User',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('password', models.CharField(max_length=128, verbose_name='password')),
                ('last_login', models.DateTimeField(blank=True, null=True, verbose_name='last login')),
                ('is_superuser', models.BooleanField(
                    default=False,
                    help_text='Designates that this user has all permissions without explicitly assigning them.',
                    verbose_name='superuser status',
                )),
                ('first_name', models.CharField(blank=True, max_length=150, verbose_name='first name')),
                ('last_name', models.CharField(blank=True, max_length=150, verbose_name='last name')),
                ('is_staff', models.BooleanField(
                    default=False,
                    help_text='Designates whether the user can log into this admin site.',
                    verbose_name='staff status',
                )),
                ('is_active', models.BooleanField(
                    default=True,
                    help_text='Designates whether this user should be treated as active.',
                    verbose_name='active',
                )),
                ('date_joined', models.DateTimeField(default=django.utils.timezone.now, verbose_name='date joined')),
                ('email', models.EmailField(
                    db_index=True,
                    error_messages={'unique': 'A user with that email already exists.'},
                    max_length=254,
                    unique=True,
                    verbose_name='email address',
                )),
                ('user_type', models.CharField(
                    choices=[
                        ('admin', 'System Administrator'),
                        ('internal', 'Internal User'),
                        ('applicant', 'Applicant'),
                    ],
                    db_index=True,
                    default='applicant',
                    max_length=20,
                )),
                ('phone_number', models.CharField(
                    blank=True,
                    max_length=20,
                    validators=[django.core.validators.RegexValidator(
                        message='Phone number must be in format: +999999999',
                        regex='^\\+?1?\\d{9,15}$',
                    )],
                )),
                ('organization', models.CharField(blank=True, max_length=200)),
                ('department', models.CharField(blank=True, max_length=100)),
                ('email_verified', models.BooleanField(default=False)),
                ('email_verification_token', models.CharField(blank=True, max_length=100)),
                ('is_two_factor_enabled', models.BooleanField(default=False)),
                ('two_factor_secret', models.CharField(blank=True, max_length=32, null=True)),
                ('two_factor_backup_codes', models.JSONField(blank=True, default=list)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('last_login_ip', models.GenericIPAddressField(blank=True, null=True)),
                ('groups', models.ManyToManyField(
                    blank=True,
                    help_text='The groups this user belongs to.',
                    related_name='user_set',
                    related_query_name='user',
                    to='auth.group',
                    verbose_name='groups',
                )),
                ('user_permissions', models.ManyToManyField(
                    blank=True,
                    help_text='Specific permissions for this user.',
                    related_name='user_set',
                    related_query_name='user',
                    to='auth.permission',
                    verbose_name='user permissions',
                )),
            ],
            options={
                'verbose_name': 'User',
                'verbose_name_plural': 'Users',
                'ordering': ['-created_at'],
                'indexes': [
                    models.Index(fields=['email', 'user_type'], name='users_user_email_user_type_idx'),
                    models.Index(fields=['created_at'], name='users_user_created_at_idx'),
                ],
            },
            managers=[
                ('objects', django.contrib.auth.models.UserManager()),
            ],
        ),
        migrations.CreateModel(
            name='UserProfile',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('user', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='profile',
                    to='users.user',
                )),
                ('date_of_birth', models.DateField(blank=True, null=True)),
                ('nationality', models.CharField(blank=True, max_length=100)),
                ('address', models.TextField(blank=True)),
                ('city', models.CharField(blank=True, max_length=100)),
                ('country', models.CharField(blank=True, max_length=100)),
                ('postal_code', models.CharField(blank=True, max_length=20)),
                ('current_job_title', models.CharField(blank=True, max_length=200)),
                ('years_of_experience', models.IntegerField(blank=True, null=True)),
                ('linkedin_url', models.URLField(blank=True)),
                ('profile_completion_percentage', models.IntegerField(default=0)),
                ('bio', models.TextField(blank=True, max_length=500)),
                ('avatar', models.ImageField(blank=True, null=True, upload_to='avatars/')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'User Profile',
                'verbose_name_plural': 'User Profiles',
            },
        ),
        migrations.CreateModel(
            name='LoginHistory',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='login_history',
                    to='users.user',
                )),
                ('timestamp', models.DateTimeField(auto_now_add=True)),
                ('ip_address', models.GenericIPAddressField()),
                ('user_agent', models.TextField()),
                ('country', models.CharField(blank=True, max_length=100)),
                ('city', models.CharField(blank=True, max_length=100)),
                ('success', models.BooleanField(default=True)),
                ('failure_reason', models.CharField(blank=True, max_length=200)),
            ],
            options={
                'verbose_name': 'Login History',
                'verbose_name_plural': 'Login Histories',
                'ordering': ['-timestamp'],
                'indexes': [
                    models.Index(fields=['user', '-timestamp'], name='users_loginhistory_user_ts_idx'),
                ],
            },
        ),
        migrations.CreateModel(
            name='PasswordResetToken',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('slug', models.SlugField(max_length=255, null=True, verbose_name='Slug Field')),
                ('token', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('expires_at', models.DateTimeField()),
                ('user', models.ForeignKey(
                    null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='password_reset_tokens',
                    to='users.user',
                )),
                ('admin_user', models.ForeignKey(
                    null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='password_reset_tokens',
                    to='users.userprofile',
                )),
            ],
            options={
                'verbose_name': 'Password Reset Token',
                'verbose_name_plural': 'Password Reset Tokens',
                'indexes': [
                    models.Index(fields=['user', 'token'], name='users_passwordresettoken_user_token_idx'),
                ],
                'constraints': [
                    models.CheckConstraint(
                        condition=(
                            models.Q(user__isnull=False, admin_user__isnull=True)
                            | models.Q(user__isnull=True, admin_user__isnull=False)
                        ),
                        name='chk_password_reset_token_one_user',
                    ),
                ],
            },
        ),
    ]
