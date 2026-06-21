# Read & write Bitbucket files

Use the `Git` connector to manipulate files in a Bitbucket Server repository over its HTTP API (with
SSH used for delete operations). All methods are async.

## Construct the client

```python
from tashtiot_apis_library import Git

git = Git(
    base_url="https://bitbucket.example.com",      # base Bitbucket URL
    token="token",                                  # HTTP token with write access
    username_or_email="user@example.com",           # service account identity
    project_key="PROJ",                             # Bitbucket project key
    repo_slug="repo-name",                          # repo name, lowercase
    default_ref="main",                             # default branch to operate on
    ssh_key_file_path="/path/to/ssh/private/key",   # SSH key (used for delete)
)
```

## Read a file

```python
content = await git.get_file_content("/path/to/values.yaml")        # returns str
```

Parse it however you like — for example, as YAML:

```python
import yaml
data = yaml.safe_load(await git.get_file_content("/app/values.yaml"))
```

## Add, modify, and delete files

```python
await git.add_file("/new/file.txt", "Add file", "hello world")
await git.modify_file("/app/values.yaml", "Bump replicas", new_yaml_str)
await git.delete_file("/old/file.txt", "Remove obsolete file")
```

Each takes a commit message; pass `branch=` to target a branch other than `default_ref`.

## List and check existence

```python
entries = await git.list_dir("/app")               # List[Tuple[name, type]]
all_files = await git.list_files_recursive("/app")  # List[str]
exists = await git.file_exists("/app/values.yaml")  # bool
```

## A complete example

```python
import asyncio
import yaml
from tashtiot_apis_library import Git

async def main():
    git = Git(
        base_url="https://bitbucket.example.com",
        token="token",
        username_or_email="user@example.com",
        project_key="PROJ",
        repo_slug="repo-name",
        default_ref="main",
        ssh_key_file_path="/path/to/ssh/private/key",
    )
    values = yaml.safe_load(await git.get_file_content("/app/values.yaml"))
    print(values)

asyncio.run(main())
```

## Errors

Operations that hit a `4xx`/`5xx` raise `GitError` (a subclass of `fastapi.HTTPException`), so raising
one inside a FastAPI route surfaces directly as an HTTP response. Import it from
`tashtiot_apis_library.connectors.errors` — see the [Errors reference](../reference/api/errors.md).

## See also

- [Connectors API reference](../reference/api/connectors.md)
- [Architecture: the three-layer connector pattern](../explanation/architecture.md)
