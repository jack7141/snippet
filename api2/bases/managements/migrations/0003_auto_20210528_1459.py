# Generated by Django 3.0.3 on 2021-05-28 05:59

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("managements", "0002_auto_20201216_1937"),
    ]

    operations = [
        migrations.CreateModel(
            name="ErrorOccur",
            fields=[
                ("error_occur_id", models.AutoField(primary_key=True, serialize=False)),
                (
                    "account_alias",
                    models.CharField(
                        editable=False, help_text="계좌번호 별칭(INDEX)", max_length=128
                    ),
                ),
                ("occured_at", models.DateTimeField(null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name="ErrorSet",
            fields=[
                (
                    "error_id",
                    models.IntegerField(
                        help_text="에러 종류", primary_key=True, serialize=False
                    ),
                ),
                ("error_msg", models.CharField(help_text="에러 메세지", max_length=50)),
                (
                    "response_manual",
                    models.CharField(help_text="대응 매뉴얼", max_length=200),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.AlterField(
            model_name="queue",
            name="status",
            field=models.SmallIntegerField(
                choices=[
                    (1, "지연중"),
                    (2, "실패"),
                    (3, "대기중"),
                    (4, "진행중"),
                    (5, "완료됨"),
                    (6, "취소됨"),
                    (7, "건너뜀"),
                ],
                default=3,
                help_text="주문 종류(1: 지연중, 2: 실패, 3: 대기중, 4: 진행중, 5: 완료됨, 6: 취소됨, 7: 건너뜀)",
            ),
        ),
        migrations.CreateModel(
            name="ErrorSolved",
            fields=[
                (
                    "error_occur",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        primary_key=True,
                        serialize=False,
                        to="managements.ErrorOccur",
                        verbose_name="error_occur_id",
                    ),
                ),
                ("solved_at", models.DateTimeField(null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.AddField(
            model_name="erroroccur",
            name="error",
            field=models.ForeignKey(
                help_text="error_occur_id",
                on_delete=django.db.models.deletion.CASCADE,
                to="managements.ErrorSet",
            ),
        ),
        migrations.AddField(
            model_name="erroroccur",
            name="order",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="order_id",
                to="managements.Queue",
            ),
        ),
    ]
