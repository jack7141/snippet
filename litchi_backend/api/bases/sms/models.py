# This is an auto-generated Django model module.
# You'll have to do the following manually to clean this up:
#   * Rearrange models' order
#   * Make sure each model has one field with primary_key=True
#   * Make sure each ForeignKey has `on_delete` set to the desired behavior.
#   * Remove `managed = False` lines if you wish to allow Django to create, modify, and delete the table
# Feel free to rename the models, but don't rename db_table values or field names.
from __future__ import unicode_literals

from django.db import models
from django.conf import settings


class ScTran(models.Model):
    tr_num = models.AutoField(db_column='TR_NUM', primary_key=True)
    tr_senddate = models.DateTimeField(db_column='TR_SENDDATE', auto_now=True)
    tr_id = models.CharField(db_column='TR_ID', max_length=16, blank=True, null=True)
    tr_sendstat = models.CharField(db_column='TR_SENDSTAT', max_length=1, default='0')
    tr_rsltstat = models.CharField(db_column='TR_RSLTSTAT', max_length=2, blank=True, null=True)
    tr_msgtype = models.CharField(db_column='TR_MSGTYPE', max_length=1, default='0')
    tr_phone = models.CharField(db_column='TR_PHONE', max_length=20, null=False, blank=False)
    tr_callback = models.CharField(db_column='TR_CALLBACK', max_length=20,
                                   blank=True, null=True, default=settings.SMS_CONTACT_NUMBER)
    tr_rsltdate = models.DateTimeField(db_column='TR_RSLTDATE', blank=True, null=True)
    tr_modified = models.DateTimeField(db_column='TR_MODIFIED', blank=True, null=True)
    tr_msg = models.CharField(db_column='TR_MSG', max_length=160, blank=True, null=True)
    tr_net = models.CharField(db_column='TR_NET', max_length=4, blank=True, null=True)
    tr_etc1 = models.CharField(db_column='TR_ETC1', max_length=160, blank=True, null=True)
    tr_etc2 = models.CharField(db_column='TR_ETC2', max_length=160, blank=True, null=True)
    tr_etc3 = models.CharField(db_column='TR_ETC3', max_length=160, blank=True, null=True)
    tr_etc4 = models.CharField(db_column='TR_ETC4', max_length=160, blank=True, null=True)
    tr_etc5 = models.CharField(db_column='TR_ETC5', max_length=160, blank=True, null=True)
    tr_etc6 = models.CharField(db_column='TR_ETC6', max_length=160, blank=True, null=True)
    tr_routeid = models.CharField(db_column='TR_ROUTEID', max_length=20, blank=True, null=True)
    tr_realsenddate = models.DateTimeField(db_column='TR_REALSENDDATE', blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'SC_TRAN'


class MmsMsg(models.Model):
    msgkey = models.AutoField(db_column='MSGKEY', primary_key=True)
    subject = models.CharField(db_column='SUBJECT', max_length=120, blank=True, null=True)
    phone = models.CharField(db_column='PHONE', max_length=15)
    callback = models.CharField(db_column='CALLBACK', max_length=15, default=settings.SMS_CONTACT_NUMBER)
    status = models.CharField(db_column='STATUS', max_length=2, default='0')
    reqdate = models.DateTimeField(db_column='REQDATE', auto_now_add=True)
    msg = models.CharField(db_column='MSG', max_length=4000, blank=True, null=True)
    file_cnt = models.IntegerField(db_column='FILE_CNT', default=0)
    file_cnt_real = models.IntegerField(db_column='FILE_CNT_REAL', blank=True, null=True)
    file_path1 = models.CharField(db_column='FILE_PATH1', max_length=512, blank=True, null=True)
    file_path1_siz = models.IntegerField(db_column='FILE_PATH1_SIZ', blank=True, null=True)
    file_path2 = models.CharField(db_column='FILE_PATH2', max_length=512, blank=True, null=True)
    file_path2_siz = models.IntegerField(db_column='FILE_PATH2_SIZ', blank=True, null=True)
    file_path3 = models.CharField(db_column='FILE_PATH3', max_length=512, blank=True, null=True)
    file_path3_siz = models.IntegerField(db_column='FILE_PATH3_SIZ', blank=True, null=True)
    file_path4 = models.CharField(db_column='FILE_PATH4', max_length=512, blank=True, null=True)
    file_path4_siz = models.IntegerField(db_column='FILE_PATH4_SIZ', blank=True, null=True)
    file_path5 = models.CharField(db_column='FILE_PATH5', max_length=512, blank=True, null=True)
    file_path5_siz = models.IntegerField(db_column='FILE_PATH5_SIZ', blank=True, null=True)
    expiretime = models.CharField(db_column='EXPIRETIME', max_length=10, default='43200')
    sentdate = models.DateTimeField(db_column='SENTDATE', blank=True, null=True)
    rsltdate = models.DateTimeField(db_column='RSLTDATE', blank=True, null=True)
    reportdate = models.DateTimeField(db_column='REPORTDATE', blank=True, null=True)
    terminateddate = models.DateTimeField(db_column='TERMINATEDDATE', blank=True, null=True)
    rslt = models.CharField(db_column='RSLT', max_length=4, blank=True, null=True)
    type = models.CharField(db_column='TYPE', max_length=2, default='0')
    telcoinfo = models.CharField(db_column='TELCOINFO', max_length=10, blank=True, null=True)
    route_id = models.CharField(db_column='ROUTE_ID', max_length=20, blank=True, null=True)
    id = models.CharField(db_column='ID', max_length=20, blank=True, null=True)
    post = models.CharField(db_column='POST', max_length=20, blank=True, null=True)
    etc1 = models.CharField(db_column='ETC1', max_length=64, blank=True, null=True)
    etc2 = models.CharField(db_column='ETC2', max_length=32, blank=True, null=True)
    etc3 = models.CharField(db_column='ETC3', max_length=32, blank=True, null=True)
    etc4 = models.IntegerField(db_column='ETC4', blank=True, null=True)
    multi_seq = models.CharField(db_column='MULTI_SEQ', max_length=10, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'MMS_MSG'
