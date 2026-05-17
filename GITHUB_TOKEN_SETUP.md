# GitHub Token Setup Instructions

## 1. Generate a New Fine-Grained PAT

1. Go to https://github.com/settings/tokens?type=beta
2. Click **Generate new token** → **Fine-grained token**
3. Set **Token name**: `MBZUAI-Intelligence-Brief`
4. Set **Expiration**: 90 days (or your preference)
5. Set **Repository access**: `Only select repositories` → `shahin-trunk/MBZUAI-Intelligence-Brief`
6. Under **Permissions**:
   - **Contents**: Access level `Read and write`
   - **Actions**: Access level `Read and write`
   - **Metadata**: Access level `Read` (auto-granted)
7. Click **Generate token** and copy the token (starts with `github_pat_...`)

Alternatively, create a **classic token** at https://github.com/settings/tokens:
1. Click **Generate new token (classic)**
2. Set scope: **`repo`** (full control)
3. Optionally also check **`workflow`**
4. Copy the token

## 2. Authenticate and Push

### Option A: Use the token directly with git push

```bash
cd /Users/shahin/PycharmProjects/audar/MBZUAI-Intelligence-Brief
git push https://shahin-trunk:YOUR_TOKEN@github.com/shahin-trunk/MBZUAI-Intelligence-Brief.git main
```

### Option B: Update git remote and push

```bash
cd /Users/shahin/PycharmProjects/audar/MBZUAI-Intelligence-Brief
git remote set-url origin https://shahin-trunk:YOUR_TOKEN@github.com/shahin-trunk/MBZUAI-Intelligence-Brief.git
git push origin main
```

### Option C: Login with gh CLI

```bash
cd /Users/shahin/PycharmProjects/audar/MBZUAI-Intelligence-Brief
echo "YOUR_TOKEN" | gh auth login --with-token
git push origin main
```

Replace `YOUR_TOKEN` with the token you generated.

## 3. Trigger the GitHub Actions Workflow

After the push succeeds:

1. Go to https://github.com/shahin-trunk/MBZUAI-Intelligence-Brief/actions/workflows/generate-audio.yml
2. Click **Run workflow**
3. Enter a brief date (e.g. `2026-05-07`)
4. Click **Run workflow**

The workflow will:
- Use the custom TTS endpoint (`https://txt2sph.audarai.com/elevenlabs`)
- Generate English audio via Claude script → Argent TTS → upload to Supabase Storage
- Save the audio URL and script to the briefs table
- Revalidate the frontend cache so the audio player appears immediately
