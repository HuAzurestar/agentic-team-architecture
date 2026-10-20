FROM python:3.12-alpine
WORKDIR /app
COPY notify.py web.html ./
RUN addgroup -S notify && adduser -S -G notify notify \
    && mkdir /data && chown notify:notify /data
USER notify
EXPOSE 17654
CMD ["python", "-u", "notify.py", "--serve", "--host", "0.0.0.0", "--database", "/data/messages.db"]
