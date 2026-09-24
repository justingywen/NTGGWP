# Azure 部署指南

專案已從 AWS（Elastic Beanstalk + RDS MySQL + S3）遷移到 Microsoft Azure。本文件取代原本的
`.ebextensions/`／`.elasticbeanstalk/`／`.platform/`，記錄在 Azure 上重新建置所需的步驟。

## 一、Azure SQL Database

1. Azure Portal 建立 **SQL Database**（Basic / Serverless 皆可，學生方案可用免費額度）。
2. 伺服器層級防火牆規則加入你的 IP，以及「允許 Azure 服務存取」（App Service 需要）。
3. 本機開發需安裝 **ODBC Driver 18 for SQL Server**（[微軟下載頁](https://learn.microsoft.com/sql/connect/odbc/download-odbc-driver-for-sql-server)）。
4. 在 `.env` 填入：
   ```
   DB_NAME=course_platform_db
   DB_USER=你的管理員帳號
   DB_PASSWORD=你的密碼
   DB_HOST=你的伺服器名稱.database.windows.net
   DB_PORT=1433
   ```
5. 建表：
   ```bash
   cd myproject
   python manage.py migrate
   ```

`myproject/myproject/settings.py` 的 `DATABASES` 已改用 `mssql-django`（`ENGINE: 'mssql'`），
連線字串預設加密（`Encrypt=yes`），符合 Azure SQL 的強制要求。

## 二、Azure Blob Storage（課程圖片／影片）

1. 建立 **Storage Account**，底下新增一個 Blob **容器（Container）**，Public access level 設為
   *Blob*（讓已上傳的圖片可直接被瀏覽器讀取；付費影片仍走 `stream_lesson_video` 的權限檢查，
   不受此影響 —— 詳見 `views.py` 的 fallback 邏輯：非本機檔案系統儲存時會改成導向 blob URL）。
2. 在「存取金鑰」複製 Storage Account 名稱與金鑰，填入 `.env`：
   ```
   AZURE_ACCOUNT_NAME=你的storage帳號
   AZURE_ACCOUNT_KEY=你的金鑰
   AZURE_CONTAINER=media
   ```
3. 沒填這三個變數時會退回本機檔案系統儲存（`myproject/media/`），僅適合本機開發，
   **正式環境（App Service）務必填寫**，因為 App Service 的檔案系統不會在重啟/擴容間保留。

## 三、Microsoft Entra ID SSO（學生登入）

1. 到 [Microsoft Entra 系統管理中心](https://entra.microsoft.com) → 應用程式註冊 → 新登錄。
2. 支援的帳戶類型視需求選擇：
   - 僅限本校 Microsoft 365 教育租戶 → 選「僅此組織目錄中的帳戶」，並把該校 Tenant ID
     填入 `.env` 的 `MICROSOFT_OAUTH_TENANT_ID`。
   - 開放任何學校/公司帳號 → 選「任何組織目錄中的帳戶」，`.env` 填 `organizations`。
   - 也開放個人 Microsoft 帳號 → 選「任何組織目錄中的帳戶及個人 Microsoft 帳戶」，
     `.env` 維持預設 `common`。
3. 重新導向 URI（平台選 **Web**）：
   - 本機開發：`http://127.0.0.1:8000/oauth/microsoft/callback/`
   - 正式環境：`https://<你的App Service網域>/oauth/microsoft/callback/`
4. 「憑證與密碼」建立一組用戶端密碼，連同應用程式（用戶端）ID 填入 `.env`：
   ```
   MICROSOFT_OAUTH_CLIENT_ID=
   MICROSOFT_OAUTH_CLIENT_SECRET=
   MICROSOFT_OAUTH_TENANT_ID=common
   ```
5. 「API 權限」預設的 `User.Read`（委派）即可，不需要額外同意管理員權限。

登入按鈕已加在登入／註冊頁（`使用 Microsoft 登入`），流程與既有的 Google／LINE 登入共用同一套
`main/oauth.py` + `Profile.microsoft_id` 的 pattern。

## 四、Azure App Service（取代 Elastic Beanstalk）

1. 建立 **App Service**（Linux，執行環境堆疊選清單中最新的 Python 版本，方案 B1 以上避免冷啟動太慢）。
2. **設定 → 環境變數（Application settings）** 填入 `.env` 內所有變數（`DB_*`、
   `AZURE_*`、`MICROSOFT_OAUTH_*`、`GOOGLE_OAUTH_*`、`LINE_LOGIN_*`、`SECRET_KEY`、
   `ALLOWED_HOSTS`、`CSRF_TRUSTED_ORIGINS` 等），另加：
   ```
   SCM_DO_BUILD_DURING_DEPLOYMENT=true
   ```
   讓 Azure 的 Oryx 建置系統在部署時自動 `pip install -r requirements.txt`。
3. `ALLOWED_HOSTS` 與 `CSRF_TRUSTED_ORIGINS` 記得加上 App Service 網域
   （例如 `your-app.azurewebsites.net`）。
4. 部署設定沿用根目錄的 `Procfile`（`gunicorn --chdir myproject --bind :8000 ...`），
   App Service 的 Python 容器預設就是連到 8000 埠，不需額外設定 Startup Command。
5. 部署後第一次要跑 migration 與 collectstatic，可在 App Service 的 **SSH 主控台**執行：
   ```bash
   cd /home/site/wwwroot/myproject
   python manage.py migrate --noinput
   python manage.py collectstatic --noinput
   ```
   或改用 `.github/workflows/azure-webapps-deploy.yml` 的 GitHub Actions 流程，把這兩行
   加進部署 job（另需在 workflow 的 secrets 設定 `AZURE_WEBAPP_PUBLISH_PROFILE`，
   從 App Service 的「取得發佈設定檔」下載後貼進 GitHub repo 的 Secrets）。
6. 大型影片上傳：Elastic Beanstalk 原本靠 `.platform/nginx` 放寬
   `client_max_body_size`；App Service 內建的反向代理預設上限已足夠涵蓋一般課程影片
   （數百 MB～GB 等級），若仍遇到 413，改到 App Service **設定 → 一般設定**開啟
   `HTTP 版本 2.0` 並確認方案未限制請求逾時。

## 五、與 Microsoft Fabric 的銜接（比賽加分項）

Azure SQL Database 可直接被 **Microsoft Fabric** 用「資料庫鏡像（Database Mirroring）」
即時鏡射進 Fabric OneLake，不需另外寫 ETL，即可在 Fabric 裡用 Power BI / Notebook
分析課程、訂單、營收資料。Fabric 工作區 → 新增項目 → 「已鏡像的 Azure SQL 資料庫」，
選這個 SQL Database 即可。
