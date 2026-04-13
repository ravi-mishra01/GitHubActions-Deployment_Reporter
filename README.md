***

# GitHub Actions Blue/Green Deployment Reporter

This utility scans multiple GitHub repositories and generates a CSV report of the **latest successful Blue and Green deployments** per repository by inspecting **GitHub Actions workflow runs**.

It is designed for release workflows where deployments are triggered by pushing tags such as:

*   **stage**: `rc...-green`, `rc...-blue`
*   **prod**: `rel...-green`, `rel...-blue`

The output includes repository name, environment, deployment color, tag, commit SHA, commit author, deployment timestamp (ET), and commit message.

***

## Features

*   ✅ Reads a list of repositories from `repos.txt`
*   ✅ Fetches workflow runs for a target workflow  
    *(default: **UnitedOps Microservice Pipeline**)*
*   ✅ Finds the **latest successful** deployment for **Blue** and **Green**
*   ✅ Pulls commit metadata (author + commit message)
*   ✅ Processes repositories in parallel for faster execution
*   ✅ Exports a timestamped CSV report

***

## How It Works

For each repository:

1.  Locates the workflow ID using the workflow name.
2.  Fetches workflow runs (paged).
3.  Filters workflow runs where:
    *   Event is `push`
    *   Conclusion is `success` (required)
    *   `head_branch` starts with the environment tag prefix (`rc` or `rel`)
4.  Classifies tags:
    *   **green** if tag matches `*green*`
    *   **blue** if tag matches `*blue*`
5.  Selects the most recent deployment for each color.
6.  Fetches commit details using the run’s `head_sha`.
7.  Writes consolidated results to a CSV file.

***

## Requirements

*   Python **3.9+** (uses `zoneinfo`)
*   GitHub token with access to the target repositories
*   Network access to `https://api.github.com`

### Python Dependencies

*   `requests`

Install dependencies:

```bash
pip install requests
```

***

## Repository List Format (`repos.txt`)

Create a file named `repos.txt` (or set `REPOS_FILE`) with repositories in `org/repo` format:

```text
my-org/service-a
my-org/service-b
# lines starting with # are ignored
my-org/service-c
```

***

## Authentication

Set a GitHub token:

```bash
export GITHUB_TOKEN="ghp_XXXXXXXXXXXXXXXXXXXX"
```

> ⚠️ If your organization uses SSO, ensure the token is SSO‑authorized.  
> Otherwise, you may encounter `401 Bad credentials`.

***

## Usage

### Stage (default)

```bash
python3 report_latest_deploys.py
```

### Explicit environment via CLI argument

```bash
python3 report_latest_deploys.py stage
python3 report_latest_deploys.py prod
```

### Environment via environment variable

```bash
export ENVIRONMENT=prod
python3 report_latest_deploys.py
```

***

## Output

The script generates a timestamped CSV file, for example:

```text
stage_latest_deploys_20260302_083012Z.csv
```

### CSV Columns

*   `repo` — repository name (`org/repo`)
*   `environment` — `stage` or `prod`
*   `color` — `blue` or `green`
*   `tag` — deployment tag detected from workflow run (`head_branch`)
*   `sha` — short commit SHA (7 characters)
*   `deployed_by` — commit author name/email
*   `deployment_time_et` — deployment time in `America/New_York`
*   `commit_comment` — sanitized commit message

***

## Configuration

All settings can be controlled via environment variables:

| Variable        | Default                         | Description                             |
| --------------- | ------------------------------- | --------------------------------------- |
| `ENVIRONMENT`   | `stage`                         | Deployment environment (`stage`/`prod`) |
| `REPOS_FILE`    | `repos.txt`                     | Repository list file                    |
| `WORKFLOW_NAME` | UnitedOps Microservice Pipeline | Workflow name to scan                   |
| `PER_PAGE`      | `50`                            | GitHub API page size                    |
| `MAX_PAGES`     | `8`                             | Max workflow run pages to scan          |
| `MAX_WORKERS`   | `6`                             | Concurrent worker threads               |
| `OUT_CSV`       | Auto-generated                  | Output CSV filename                     |

### Example

```bash
export WORKFLOW_NAME="UnitedOps Microservice Pipeline"
export REPOS_FILE="repos.txt"
export MAX_WORKERS=10

python3 report_latest_deploys.py prod
```

***

## Tag Naming Convention

Tags must:

*   Start with:
    *   `rc` for **stage**
    *   `rel` for **prod**
*   Contain either `blue` or `green`
*   Use `-` or `_` as separators

### Valid Examples

*   `rc-1.2.3-green`
*   `rc_2026.03.01_blue`
*   `rel-2026.02.15-green`

***

## Troubleshooting

### Workflow Not Found

**Error:**

    Workflow '...' not found

*   Verify the workflow name in GitHub Actions.
*   Ensure `WORKFLOW_NAME` matches exactly.

### 401 Bad Credentials

*   Confirm `GITHUB_TOKEN` is valid.
*   Ensure SSO authorization if required.

### Missing Blue/Green Deployments

*   Confirm deployments are triggered by **push events to tags**.
*   Ensure correct tag prefix (`rc` / `rel`) and color (`blue` / `green`).

***

## Possible Enhancements

*   Read “deployed by” from tag annotations or GitHub Releases
*   Make timezone configurable
*   Support additional workflow triggers (`workflow_dispatch`, `pull_request`)

***

## License

Add your preferred license (MIT, Apache‑2.0, etc.).

***

If you want, I can also:

*   Shorten this for an **internal/enterprise README**
*   Add **GitHub badges**
*   Align terminology with **platform or SRE standards**
*   Clean up the script to match this documentation exactly

Just tell me 👍
