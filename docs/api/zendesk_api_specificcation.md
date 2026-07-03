# Articles

Articles are content items such as help topics or tech notes contained in [sections](/api-reference/help_center/help-center-api/sections/). See [Creating and editing articles in the knowledge base](https://support.zendesk.com/hc/en-us/articles/4408839258778) in Zendesk help.

Guide admins can create articles and edit all existing articles in the knowledge base. Agents who are not Guide admins can create and edit articles if they have [management permissions](https://support.zendesk.com/hc/en-us/articles/4408827952538). End users can neither create nor edit articles. See [Understanding Guide roles and privileges](https://support.zendesk.com/hc/en-us/articles/4408827842458).

The Articles API has certain limitations if content blocks have been enabled for one or more articles in the help center. See [Help Center API limitations with content blocks](/documentation/help_center/help-center-api/using-the-help-center-api/content-blocks-limitations/).

### JSON format

Articles are represented as JSON objects with the following properties:

| Name                | Type    | Read-only | Mandatory | Description                                                                                                                                                                                                                                                     |
| ------------------- | ------- | --------- | --------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| author_id           | integer | false     | false     | The id of the user who wrote the article (set to the user who made the request on create by default)                                                                                                                                                            |
| body                | string  | false     | false     | HTML body of the article. Unsafe tags and attributes may be removed before display. For a list of safe tags and attributes, see [Allowing unsafe HTML in Help Center articles](https://support.zendesk.com/hc/en-us/articles/115015895948) in Zendesk help      |
| comments_disabled   | boolean | false     | false     | True if comments are disabled; false otherwise                                                                                                                                                                                                                  |
| content_tag_ids     | array   | false     | false     | The list of content tags attached to the article                                                                                                                                                                                                                |
| created_at          | string  | true      | false     | The time the article was created                                                                                                                                                                                                                                |
| draft               | boolean | true      | false     | True if the translation for the current locale is a draft; false otherwise. false by default. Can be set when creating but not when updating. For updating, see Translations                                                                                    |
| edited_at           | string  | true      | false     | The time the article was last edited in its displayed locale                                                                                                                                                                                                    |
| html_url            | string  | true      | false     | The url of the article in Help Center                                                                                                                                                                                                                           |
| id                  | integer | true      | false     | Automatically assigned when the article is created                                                                                                                                                                                                              |
| label_names         | array   | false     | false     | An array of label names associated with this article. By default no label names are used. Only available on certain plans                                                                                                                                       |
| locale              | string  | false     | true      | The locale that the article is being displayed in                                                                                                                                                                                                               |
| outdated            | boolean | true      | false     | Deprecated. Always false because the source translation is always the most up-to-date translation                                                                                                                                                               |
| outdated_locales    | array   | true      | false     | Locales in which the article was marked as outdated                                                                                                                                                                                                             |
| permission_group_id | integer | false     | true      | The id of the permission group which defines who can edit and publish this article                                                                                                                                                                              |
| position            | integer | false     | false     | The position of this article in the article list. 0 by default                                                                                                                                                                                                  |
| promoted            | boolean | false     | false     | True if this article is promoted; false otherwise. false by default                                                                                                                                                                                             |
| section_id          | integer | false     | false     | The id of the section to which this article belongs                                                                                                                                                                                                             |
| source_locale       | string  | true      | false     | The source (default) locale of the article                                                                                                                                                                                                                      |
| title               | string  | false     | true      | The title of the article                                                                                                                                                                                                                                        |
| updated_at          | string  | true      | false     | The time the article was last updated                                                                                                                                                                                                                           |
| url                 | string  | true      | false     | The API url of the article                                                                                                                                                                                                                                      |
| user_segment_id     | integer | false     | false     | The id of the user segment which defines who can see this article. Set to null to make it accessible to everyone. Either user_segment_id or user_segment_ids must be specified                                                                                  |
| user_segment_ids    | array   | false     | false     | List of user segment ids which define who can view this article. Set to an empty list to make it accessible to everyone. For Enterprise plans only this may contain more than one user_segment_id. Either user_segment_id or user_segment_ids must be specified |
| vote_count          | integer | true      | false     | The total number of upvotes and downvotes                                                                                                                                                                                                                       |
| vote_sum            | integer | true      | false     | The sum of upvotes (+1) and downvotes (-1), which may be positive or negative                                                                                                                                                                                   |

#### Example

```json

{

"author_id": 3465,

"comments_disabled": false,

"id": 1635,

"locale": "en",

"permission_group_id": 13,

"title": "The article",

"user_segment_id": 12

}
```

### List Articles

- `GET /api/v2/help_center/articles`

These endpoints let you list all articles in Help Center, all articles in a given
category or section, or all the articles authored by a specific agent. You can
also list all articles with metadata that changed since a specified [start time](#start-time).

`{/locale}` is required only for end users or anonymous users. Admins and agents can omit it.

You can also use the Search API to list articles. See [Search](/api-reference/help_center/help-center-api/search).

#### Allowed for

- Agents
- End users
- Anonymous users

The response lists only the articles that the requesting agent,
end user, or anonymous user can view in Help Center.

#### Pagination

- Cursor pagination (recommended)
- Offset pagination

See [Pagination](/api-reference/introduction/pagination/).

#### Sorting

You can sort the results with the `sort_by` and `sort_order` query string parameters.

GET /api/v2/help_center/en-us/articles.json?sort_by=updated_at&sort_order=asc

The `sort_by` parameter can have one of the following values:

| value        | description                                                      |
| ------------ | ---------------------------------------------------------------- |
| `position`   | order set manually using the Arrange Content page. Default order |
| `title`      | order alphabetically by title                                    |
| `created_at` | order by creation time                                           |
| `updated_at` | order by update time                                             |
| `edited_at`  | order by the last time the title or body was edited              |

When sorting by `title`, the endpoint must specify a locale for the titles. Example:

/api/v2/help_center/en-us/articles.json?sort_by=title

Sorting by `edited_at` also requires a locale. The value specifies the locale in which the title or body was last changed.

The `sort_order` parameter can have one of the following values:

| value  | description      |
| ------ | ---------------- |
| `asc`  | ascending order  |
| `desc` | descending order |

Note that if sorting parameters are not passed to the section-scoped articles endpoint (`/api/v2/help_center/{locale}/sections/{section_id}/articles.json`), articles will be returned in the order defined on the section itself. See [Organizing knowledge base content in categories and sections](https://support.zendesk.com/hc/en-us/articles/4408845897370-Organizing-knowledge-base-content-in-categories-and-sections#topic_m3v_gq4_kk) for more information about defining sort orders on sections.

#### Options

##### Start Time

You can use the incremental article endpoint to list all the articles that were
updated since a certain date and time. The endpoint takes a `start_time` parameter
with a [Unix epoch time](http://www.epochconverter.com/). Example:

/api/v2/help_center/incremental/articles.json?start_time=1404345231

##### Label Names

You can specify that only articles with specific labels should be returned by adding
a `label_names` parameter. The parameter takes a comma-separated list of up to 10 label
names. Example:

/api/v2/help_center/en-us/articles.json?label_names=photos,camera

Only articles that have all the labels are returned. For example, `label_names=photos,camera` returns all articles that have both 'photo' AND 'camera' labels. If you want the articles that have either 'photo' OR 'camera' labels, you can use the [Search Article](/api-reference/help_center/help-center-api/search/#search-articles) endpoint with the `label_names` parameter (Professional and Enterprise).

Matching is case-sensitive. For example, 'camera' matches 'camera' but not 'Camera'.

#### Sideloads

The following sideloads are supported:

| Name         | Will sideload                                          |
| ------------ | ------------------------------------------------------ |
| users        | the author                                             |
| sections     | the section                                            |
| categories   | the category                                           |
| translations | the article, section and category translations, if any |

Unlike other sideloads, translations are embedded within the article because they're
not shared between resources.
Section and category translations are only sideloaded if present.

#### Parameters

| Name        | Type    | In    | Required | Description                                                                                                              |
| ----------- | ------- | ----- | -------- | ------------------------------------------------------------------------------------------------------------------------ |
| label_names | string  | Query | false    | Only articles that have all the labels are returned.                                                                     |
| sort_by     | string  | Query | false    | Sorts the articles by one of the accepted values. Allowed values are "position", "title", "created_at", or "updated_at". |
| sort_order  | string  | Query | false    | Selects the order of the results. Allowed values are "asc", or "desc".                                                   |
| start_time  | integer | Query | false    | You can use the incremental article endpoint to list all the articles that were updated since a certain date and time.   |

#### Code Samples

**Python**

```python

import requests

from requests.auth import HTTPBasicAuth

url = "https://support.zendesk.com/api/v2/help_center/articles?label_names=photos%2Ccamera&sort_by=&sort_order=&start_time=1404345231"

headers = {

    "Content-Type": "application/json",

}

email_address = 'your_email_address'

api_token = 'your_api_token'

# Use basic authentication

auth = HTTPBasicAuth(f'{email_address}/token', api_token)

response = requests.request(

    "GET",

    url,

    auth=auth,

    headers=headers

)

print(response.text)
```

#### Example response(s)

**200 OK**

```json

// Status 200 OK

{

"articles": [

    {

      "author_id": 888887,

      "draft": true,

      "id": 35467,

      "locale": "en",

      "permission_group_id": 123,

      "title": "Article title",

      "user_segment_id": 12

    }

]

}
```

### Archive Article

- `DELETE /api/v2/help_center/articles/{article_id}`

Archives the article. You can restore the article using the Help Center user interface. See [Viewing and restoring archived articles](https://support.zendesk.com/hc/en-us/articles/4408822193434).

#### Allowed for

- Agents

#### Parameters

| Name       | Type    | In   | Required | Description                  |
| ---------- | ------- | ---- | -------- | ---------------------------- |
| article_id | integer | Path | true     | The unique ID of the article |

#### Code Samples

**Python**

```python

import requests

from requests.auth import HTTPBasicAuth

url = "https://support.zendesk.com/api/v2/help_center/articles/360026053753"

headers = {

    "Content-Type": "application/json",

}

email_address = 'your_email_address'

api_token = 'your_api_token'

# Use basic authentication

auth = HTTPBasicAuth(f'{email_address}/token', api_token)

response = requests.request(

    "DELETE",

    url,

    auth=auth,

    headers=headers

)

print(response.text)
```

#### Example response(s)

**204 No Content**

// Status 204 No Content

null

### List Articles in Category

- `GET /api/v2/help_center/categories/{category_id}/articles`

These endpoints let you list all articles in Help Center, all articles in a given
category or section, or all the articles authored by a specific agent. You can
also list all articles with metadata that changed since a specified [start time](#start-time).

`{/locale}` is required only for end users or anonymous users. Admins and agents can omit it.

You can also use the Search API to list articles. See [Search](/api-reference/help_center/help-center-api/search).

#### Allowed for

- Agents
- End users
- Anonymous users

The response lists only the articles that the requesting agent,
end user, or anonymous user can view in Help Center.

#### Pagination

- Cursor pagination (recommended)
- Offset pagination

See [Pagination](/api-reference/introduction/pagination/).

#### Sorting

You can sort the results with the `sort_by` and `sort_order` query string parameters.

GET /api/v2/help_center/en-us/articles.json?sort_by=updated_at&sort_order=asc

The `sort_by` parameter can have one of the following values:

| value        | description                                                      |
| ------------ | ---------------------------------------------------------------- |
| `position`   | order set manually using the Arrange Content page. Default order |
| `title`      | order alphabetically by title                                    |
| `created_at` | order by creation time                                           |
| `updated_at` | order by update time                                             |
| `edited_at`  | order by the last time the title or body was edited              |

When sorting by `title`, the endpoint must specify a locale for the titles. Example:

/api/v2/help_center/en-us/articles.json?sort_by=title

Sorting by `edited_at` also requires a locale. The value specifies the locale in which the title or body was last changed.

The `sort_order` parameter can have one of the following values:

| value  | description      |
| ------ | ---------------- |
| `asc`  | ascending order  |
| `desc` | descending order |

Note that if sorting parameters are not passed to the section-scoped articles endpoint (`/api/v2/help_center/{locale}/sections/{section_id}/articles.json`), articles will be returned in the order defined on the section itself. See [Organizing knowledge base content in categories and sections](https://support.zendesk.com/hc/en-us/articles/4408845897370-Organizing-knowledge-base-content-in-categories-and-sections#topic_m3v_gq4_kk) for more information about defining sort orders on sections.

#### Options

##### Start Time

You can use the incremental article endpoint to list all the articles that were
updated since a certain date and time. The endpoint takes a `start_time` parameter
with a [Unix epoch time](http://www.epochconverter.com/). Example:

/api/v2/help_center/incremental/articles.json?start_time=1404345231

##### Label Names

You can specify that only articles with specific labels should be returned by adding
a `label_names` parameter. The parameter takes a comma-separated list of up to 10 label
names. Example:

/api/v2/help_center/en-us/articles.json?label_names=photos,camera

Only articles that have all the labels are returned. For example, `label_names=photos,camera` returns all articles that have both 'photo' AND 'camera' labels. If you want the articles that have either 'photo' OR 'camera' labels, you can use the [Search Article](/api-reference/help_center/help-center-api/search/#search-articles) endpoint with the `label_names` parameter (Professional and Enterprise).

Matching is case-sensitive. For example, 'camera' matches 'camera' but not 'Camera'.

#### Sideloads

The following sideloads are supported:

| Name         | Will sideload                                          |
| ------------ | ------------------------------------------------------ |
| users        | the author                                             |
| sections     | the section                                            |
| categories   | the category                                           |
| translations | the article, section and category translations, if any |

Unlike other sideloads, translations are embedded within the article because they're
not shared between resources.
Section and category translations are only sideloaded if present.

#### Parameters

| Name        | Type    | In    | Required | Description                                                                                                              |
| ----------- | ------- | ----- | -------- | ------------------------------------------------------------------------------------------------------------------------ |
| label_names | string  | Query | false    | Only articles that have all the labels are returned.                                                                     |
| sort_by     | string  | Query | false    | Sorts the articles by one of the accepted values. Allowed values are "position", "title", "created_at", or "updated_at". |
| sort_order  | string  | Query | false    | Selects the order of the results. Allowed values are "asc", or "desc".                                                   |
| start_time  | integer | Query | false    | You can use the incremental article endpoint to list all the articles that were updated since a certain date and time.   |
| category_id | integer | Path  | true     | The unique ID of the category                                                                                            |

#### Code Samples

**Python**

```python

import requests

from requests.auth import HTTPBasicAuth

url = "https://support.zendesk.com/api/v2/help_center/categories/360002011513/articles?label_names=photos%2Ccamera&sort_by=&sort_order=&start_time=1404345231"

headers = {

    "Content-Type": "application/json",

}

email_address = 'your_email_address'

api_token = 'your_api_token'

# Use basic authentication

auth = HTTPBasicAuth(f'{email_address}/token', api_token)

response = requests.request(

    "GET",

    url,

    auth=auth,

    headers=headers

)

print(response.text)
```

#### Example response(s)

**200 OK**

```json

// Status 200 OK

{

"articles": [

    {

      "author_id": 888887,

      "draft": true,

      "id": 35467,

      "locale": "en",

      "permission_group_id": 123,

      "title": "Article title",

      "user_segment_id": 12

    }

]

}
```

### List Articles Incrementally

- `GET /api/v2/help_center/incremental/articles`

These endpoints let you list all articles in Help Center, all articles in a given
category or section, or all the articles authored by a specific agent. You can
also list all articles with metadata that changed since a specified [start time](#start-time).

`{/locale}` is required only for end users or anonymous users. Admins and agents can omit it.

You can also use the Search API to list articles. See [Search](/api-reference/help_center/help-center-api/search).

#### Allowed for

- Agents
- End users
- Anonymous users

The response lists only the articles that the requesting agent,
end user, or anonymous user can view in Help Center.

#### Pagination

- Cursor pagination (recommended)
- Offset pagination

See [Pagination](/api-reference/introduction/pagination/).

#### Sorting

You can sort the results with the `sort_by` and `sort_order` query string parameters.

GET /api/v2/help_center/en-us/articles.json?sort_by=updated_at&sort_order=asc

The `sort_by` parameter can have one of the following values:

| value        | description                                                      |
| ------------ | ---------------------------------------------------------------- |
| `position`   | order set manually using the Arrange Content page. Default order |
| `title`      | order alphabetically by title                                    |
| `created_at` | order by creation time                                           |
| `updated_at` | order by update time                                             |
| `edited_at`  | order by the last time the title or body was edited              |

When sorting by `title`, the endpoint must specify a locale for the titles. Example:

/api/v2/help_center/en-us/articles.json?sort_by=title

Sorting by `edited_at` also requires a locale. The value specifies the locale in which the title or body was last changed.

The `sort_order` parameter can have one of the following values:

| value  | description      |
| ------ | ---------------- |
| `asc`  | ascending order  |
| `desc` | descending order |

Note that if sorting parameters are not passed to the section-scoped articles endpoint (`/api/v2/help_center/{locale}/sections/{section_id}/articles.json`), articles will be returned in the order defined on the section itself. See [Organizing knowledge base content in categories and sections](https://support.zendesk.com/hc/en-us/articles/4408845897370-Organizing-knowledge-base-content-in-categories-and-sections#topic_m3v_gq4_kk) for more information about defining sort orders on sections.

#### Options

##### Start Time

You can use the incremental article endpoint to list all the articles that were
updated since a certain date and time. The endpoint takes a `start_time` parameter
with a [Unix epoch time](http://www.epochconverter.com/). Example:

/api/v2/help_center/incremental/articles.json?start_time=1404345231

##### Label Names

You can specify that only articles with specific labels should be returned by adding
a `label_names` parameter. The parameter takes a comma-separated list of up to 10 label
names. Example:

/api/v2/help_center/en-us/articles.json?label_names=photos,camera

Only articles that have all the labels are returned. For example, `label_names=photos,camera` returns all articles that have both 'photo' AND 'camera' labels. If you want the articles that have either 'photo' OR 'camera' labels, you can use the [Search Article](/api-reference/help_center/help-center-api/search/#search-articles) endpoint with the `label_names` parameter (Professional and Enterprise).

Matching is case-sensitive. For example, 'camera' matches 'camera' but not 'Camera'.

#### Sideloads

The following sideloads are supported:

| Name         | Will sideload                                          |
| ------------ | ------------------------------------------------------ |
| users        | the author                                             |
| sections     | the section                                            |
| categories   | the category                                           |
| translations | the article, section and category translations, if any |

Unlike other sideloads, translations are embedded within the article because they're
not shared between resources.
Section and category translations are only sideloaded if present.

#### Parameters

| Name        | Type    | In    | Required | Description                                                                                                              |
| ----------- | ------- | ----- | -------- | ------------------------------------------------------------------------------------------------------------------------ |
| label_names | string  | Query | false    | Only articles that have all the labels are returned.                                                                     |
| sort_by     | string  | Query | false    | Sorts the articles by one of the accepted values. Allowed values are "position", "title", "created_at", or "updated_at". |
| sort_order  | string  | Query | false    | Selects the order of the results. Allowed values are "asc", or "desc".                                                   |
| start_time  | integer | Query | false    | You can use the incremental article endpoint to list all the articles that were updated since a certain date and time.   |

#### Code Samples

**Python**

```python

import requests

from requests.auth import HTTPBasicAuth

url = "https://support.zendesk.com/api/v2/help_center/incremental/articles?label_names=photos%2Ccamera&sort_by=&sort_order=&start_time=1404345231"

headers = {

    "Content-Type": "application/json",

}

email_address = 'your_email_address'

api_token = 'your_api_token'

# Use basic authentication

auth = HTTPBasicAuth(f'{email_address}/token', api_token)

response = requests.request(

    "GET",

    url,

    auth=auth,

    headers=headers

)

print(response.text)
```

#### Example response(s)

**200 OK**

```json

// Status 200 OK

{

"articles": [

    {

      "author_id": 888887,

      "draft": true,

      "id": 35467,

      "locale": "en",

      "permission_group_id": 123,

      "title": "Article title",

      "user_segment_id": 12

    }

]

}
```

### List Articles in Section

- `GET /api/v2/help_center/sections/{section_id}/articles`

These endpoints let you list all articles in Help Center, all articles in a given
category or section, or all the articles authored by a specific agent. You can
also list all articles with metadata that changed since a specified [start time](#start-time).

`{/locale}` is required only for end users or anonymous users. Admins and agents can omit it.

You can also use the Search API to list articles. See [Search](/api-reference/help_center/help-center-api/search).

#### Allowed for

- Agents
- End users
- Anonymous users

The response lists only the articles that the requesting agent,
end user, or anonymous user can view in Help Center.

#### Pagination

- Cursor pagination (recommended)
- Offset pagination

See [Pagination](/api-reference/introduction/pagination/).

#### Sorting

You can sort the results with the `sort_by` and `sort_order` query string parameters.

GET /api/v2/help_center/en-us/articles.json?sort_by=updated_at&sort_order=asc

The `sort_by` parameter can have one of the following values:

| value        | description                                                      |
| ------------ | ---------------------------------------------------------------- |
| `position`   | order set manually using the Arrange Content page. Default order |
| `title`      | order alphabetically by title                                    |
| `created_at` | order by creation time                                           |
| `updated_at` | order by update time                                             |
| `edited_at`  | order by the last time the title or body was edited              |

When sorting by `title`, the endpoint must specify a locale for the titles. Example:

/api/v2/help_center/en-us/articles.json?sort_by=title

Sorting by `edited_at` also requires a locale. The value specifies the locale in which the title or body was last changed.

The `sort_order` parameter can have one of the following values:

| value  | description      |
| ------ | ---------------- |
| `asc`  | ascending order  |
| `desc` | descending order |

Note that if sorting parameters are not passed to the section-scoped articles endpoint (`/api/v2/help_center/{locale}/sections/{section_id}/articles.json`), articles will be returned in the order defined on the section itself. See [Organizing knowledge base content in categories and sections](https://support.zendesk.com/hc/en-us/articles/4408845897370-Organizing-knowledge-base-content-in-categories-and-sections#topic_m3v_gq4_kk) for more information about defining sort orders on sections.

#### Options

##### Start Time

You can use the incremental article endpoint to list all the articles that were
updated since a certain date and time. The endpoint takes a `start_time` parameter
with a [Unix epoch time](http://www.epochconverter.com/). Example:

/api/v2/help_center/incremental/articles.json?start_time=1404345231

##### Label Names

You can specify that only articles with specific labels should be returned by adding
a `label_names` parameter. The parameter takes a comma-separated list of up to 10 label
names. Example:

/api/v2/help_center/en-us/articles.json?label_names=photos,camera

Only articles that have all the labels are returned. For example, `label_names=photos,camera` returns all articles that have both 'photo' AND 'camera' labels. If you want the articles that have either 'photo' OR 'camera' labels, you can use the [Search Article](/api-reference/help_center/help-center-api/search/#search-articles) endpoint with the `label_names` parameter (Professional and Enterprise).

Matching is case-sensitive. For example, 'camera' matches 'camera' but not 'Camera'.

#### Sideloads

The following sideloads are supported:

| Name         | Will sideload                                          |
| ------------ | ------------------------------------------------------ |
| users        | the author                                             |
| sections     | the section                                            |
| categories   | the category                                           |
| translations | the article, section and category translations, if any |

Unlike other sideloads, translations are embedded within the article because they're
not shared between resources.
Section and category translations are only sideloaded if present.

#### Parameters

| Name        | Type    | In    | Required | Description                                                                                                              |
| ----------- | ------- | ----- | -------- | ------------------------------------------------------------------------------------------------------------------------ |
| label_names | string  | Query | false    | Only articles that have all the labels are returned.                                                                     |
| sort_by     | string  | Query | false    | Sorts the articles by one of the accepted values. Allowed values are "position", "title", "created_at", or "updated_at". |
| sort_order  | string  | Query | false    | Selects the order of the results. Allowed values are "asc", or "desc".                                                   |
| start_time  | integer | Query | false    | You can use the incremental article endpoint to list all the articles that were updated since a certain date and time.   |
| section_id  | integer | Path  | true     | The unique ID of the section                                                                                             |

#### Code Samples

**Python**

```python

import requests

from requests.auth import HTTPBasicAuth

url = "https://support.zendesk.com/api/v2/help_center/sections/360004785313/articles?label_names=photos%2Ccamera&sort_by=&sort_order=&start_time=1404345231"

headers = {

    "Content-Type": "application/json",

}

email_address = 'your_email_address'

api_token = 'your_api_token'

# Use basic authentication

auth = HTTPBasicAuth(f'{email_address}/token', api_token)

response = requests.request(

    "GET",

    url,

    auth=auth,

    headers=headers

)

print(response.text)
```

#### Example response(s)

**200 OK**

```json

// Status 200 OK

{

"articles": [

    {

      "author_id": 888887,

      "draft": true,

      "id": 35467,

      "locale": "en",

      "permission_group_id": 123,

      "title": "Article title",

      "user_segment_id": 12

    }

]

}
```

### List Articles by User

- `GET /api/v2/help_center/users/{user_id}/articles`

These endpoints let you list all articles in Help Center, all articles in a given
category or section, or all the articles authored by a specific agent. You can
also list all articles with metadata that changed since a specified [start time](#start-time).

`{/locale}` is required only for end users or anonymous users. Admins and agents can omit it.

You can also use the Search API to list articles. See [Search](/api-reference/help_center/help-center-api/search).

#### Allowed for

- Agents
- End users
- Anonymous users

The response lists only the articles that the requesting agent,
end user, or anonymous user can view in Help Center.

#### Pagination

- Cursor pagination (recommended)
- Offset pagination

See [Pagination](/api-reference/introduction/pagination/).

#### Sorting

You can sort the results with the `sort_by` and `sort_order` query string parameters.

GET /api/v2/help_center/en-us/articles.json?sort_by=updated_at&sort_order=asc

The `sort_by` parameter can have one of the following values:

| value        | description                                                      |
| ------------ | ---------------------------------------------------------------- |
| `position`   | order set manually using the Arrange Content page. Default order |
| `title`      | order alphabetically by title                                    |
| `created_at` | order by creation time                                           |
| `updated_at` | order by update time                                             |
| `edited_at`  | order by the last time the title or body was edited              |

When sorting by `title`, the endpoint must specify a locale for the titles. Example:

/api/v2/help_center/en-us/articles.json?sort_by=title

Sorting by `edited_at` also requires a locale. The value specifies the locale in which the title or body was last changed.

The `sort_order` parameter can have one of the following values:

| value  | description      |
| ------ | ---------------- |
| `asc`  | ascending order  |
| `desc` | descending order |

Note that if sorting parameters are not passed to the section-scoped articles endpoint (`/api/v2/help_center/{locale}/sections/{section_id}/articles.json`), articles will be returned in the order defined on the section itself. See [Organizing knowledge base content in categories and sections](https://support.zendesk.com/hc/en-us/articles/4408845897370-Organizing-knowledge-base-content-in-categories-and-sections#topic_m3v_gq4_kk) for more information about defining sort orders on sections.

#### Options

##### Start Time

You can use the incremental article endpoint to list all the articles that were
updated since a certain date and time. The endpoint takes a `start_time` parameter
with a [Unix epoch time](http://www.epochconverter.com/). Example:

/api/v2/help_center/incremental/articles.json?start_time=1404345231

##### Label Names

You can specify that only articles with specific labels should be returned by adding
a `label_names` parameter. The parameter takes a comma-separated list of up to 10 label
names. Example:

/api/v2/help_center/en-us/articles.json?label_names=photos,camera

Only articles that have all the labels are returned. For example, `label_names=photos,camera` returns all articles that have both 'photo' AND 'camera' labels. If you want the articles that have either 'photo' OR 'camera' labels, you can use the [Search Article](/api-reference/help_center/help-center-api/search/#search-articles) endpoint with the `label_names` parameter (Professional and Enterprise).

Matching is case-sensitive. For example, 'camera' matches 'camera' but not 'Camera'.

#### Sideloads

The following sideloads are supported:

| Name         | Will sideload                                          |
| ------------ | ------------------------------------------------------ |
| users        | the author                                             |
| sections     | the section                                            |
| categories   | the category                                           |
| translations | the article, section and category translations, if any |

Unlike other sideloads, translations are embedded within the article because they're
not shared between resources.
Section and category translations are only sideloaded if present.

#### Parameters

| Name        | Type    | In    | Required | Description                                                                                                              |
| ----------- | ------- | ----- | -------- | ------------------------------------------------------------------------------------------------------------------------ |
| label_names | string  | Query | false    | Only articles that have all the labels are returned.                                                                     |
| sort_by     | string  | Query | false    | Sorts the articles by one of the accepted values. Allowed values are "position", "title", "created_at", or "updated_at". |
| sort_order  | string  | Query | false    | Selects the order of the results. Allowed values are "asc", or "desc".                                                   |
| start_time  | integer | Query | false    | You can use the incremental article endpoint to list all the articles that were updated since a certain date and time.   |
| user_id     | integer | Path  | true     | The unique ID of the user                                                                                                |

#### Code Samples

**Python**

```python

import requests

from requests.auth import HTTPBasicAuth

url = "https://support.zendesk.com/api/v2/help_center/users/1234/articles?label_names=photos%2Ccamera&sort_by=&sort_order=&start_time=1404345231"

headers = {

    "Content-Type": "application/json",

}

email_address = 'your_email_address'

api_token = 'your_api_token'

# Use basic authentication

auth = HTTPBasicAuth(f'{email_address}/token', api_token)

response = requests.request(

    "GET",

    url,

    auth=auth,

    headers=headers

)

print(response.text)
```

#### Example response(s)

**200 OK**

```json

// Status 200 OK

{

"articles": [

    {

      "author_id": 888887,

      "draft": true,

      "id": 35467,

      "locale": "en",

      "permission_group_id": 123,

      "title": "Article title",

      "user_segment_id": 12

    }

]

}
```

### List Articles by Locale

- `GET /api/v2/help_center/{locale}/articles`

These endpoints let you list all articles in Help Center, all articles in a given
category or section, or all the articles authored by a specific agent. You can
also list all articles with metadata that changed since a specified [start time](#start-time).

`{/locale}` is required only for end users or anonymous users. Admins and agents can omit it.

You can also use the Search API to list articles. See [Search](/api-reference/help_center/help-center-api/search).

#### Allowed for

- Agents
- End users
- Anonymous users

The response lists only the articles that the requesting agent,
end user, or anonymous user can view in Help Center.

#### Pagination

- Cursor pagination (recommended)
- Offset pagination

See [Pagination](/api-reference/introduction/pagination/).

#### Sorting

You can sort the results with the `sort_by` and `sort_order` query string parameters.

GET /api/v2/help_center/en-us/articles.json?sort_by=updated_at&sort_order=asc

The `sort_by` parameter can have one of the following values:

| value        | description                                                      |
| ------------ | ---------------------------------------------------------------- |
| `position`   | order set manually using the Arrange Content page. Default order |
| `title`      | order alphabetically by title                                    |
| `created_at` | order by creation time                                           |
| `updated_at` | order by update time                                             |
| `edited_at`  | order by the last time the title or body was edited              |

When sorting by `title`, the endpoint must specify a locale for the titles. Example:

/api/v2/help_center/en-us/articles.json?sort_by=title

Sorting by `edited_at` also requires a locale. The value specifies the locale in which the title or body was last changed.

The `sort_order` parameter can have one of the following values:

| value  | description      |
| ------ | ---------------- |
| `asc`  | ascending order  |
| `desc` | descending order |

Note that if sorting parameters are not passed to the section-scoped articles endpoint (`/api/v2/help_center/{locale}/sections/{section_id}/articles.json`), articles will be returned in the order defined on the section itself. See [Organizing knowledge base content in categories and sections](https://support.zendesk.com/hc/en-us/articles/4408845897370-Organizing-knowledge-base-content-in-categories-and-sections#topic_m3v_gq4_kk) for more information about defining sort orders on sections.

#### Options

##### Start Time

You can use the incremental article endpoint to list all the articles that were
updated since a certain date and time. The endpoint takes a `start_time` parameter
with a [Unix epoch time](http://www.epochconverter.com/). Example:

/api/v2/help_center/incremental/articles.json?start_time=1404345231

##### Label Names

You can specify that only articles with specific labels should be returned by adding
a `label_names` parameter. The parameter takes a comma-separated list of up to 10 label
names. Example:

/api/v2/help_center/en-us/articles.json?label_names=photos,camera

Only articles that have all the labels are returned. For example, `label_names=photos,camera` returns all articles that have both 'photo' AND 'camera' labels. If you want the articles that have either 'photo' OR 'camera' labels, you can use the [Search Article](/api-reference/help_center/help-center-api/search/#search-articles) endpoint with the `label_names` parameter (Professional and Enterprise).

Matching is case-sensitive. For example, 'camera' matches 'camera' but not 'Camera'.

#### Sideloads

The following sideloads are supported:

| Name         | Will sideload                                          |
| ------------ | ------------------------------------------------------ |
| users        | the author                                             |
| sections     | the section                                            |
| categories   | the category                                           |
| translations | the article, section and category translations, if any |

Unlike other sideloads, translations are embedded within the article because they're
not shared between resources.
Section and category translations are only sideloaded if present.

#### Parameters

| Name        | Type    | In    | Required | Description                                                                                                              |
| ----------- | ------- | ----- | -------- | ------------------------------------------------------------------------------------------------------------------------ |
| label_names | string  | Query | false    | Only articles that have all the labels are returned.                                                                     |
| sort_by     | string  | Query | false    | Sorts the articles by one of the accepted values. Allowed values are "position", "title", "created_at", or "updated_at". |
| sort_order  | string  | Query | false    | Selects the order of the results. Allowed values are "asc", or "desc".                                                   |
| start_time  | integer | Query | false    | You can use the incremental article endpoint to list all the articles that were updated since a certain date and time.   |
| locale      | string  | Path  | true     | The locale the item is displayed in                                                                                      |

#### Code Samples

**Python**

```python

import requests

from requests.auth import HTTPBasicAuth

url = "https://support.zendesk.com/api/v2/help_center/en-us/articles?label_names=photos%2Ccamera&sort_by=&sort_order=&start_time=1404345231"

headers = {

    "Content-Type": "application/json",

}

email_address = 'your_email_address'

api_token = 'your_api_token'

# Use basic authentication

auth = HTTPBasicAuth(f'{email_address}/token', api_token)

response = requests.request(

    "GET",

    url,

    auth=auth,

    headers=headers

)

print(response.text)
```

#### Example response(s)

**200 OK**

```json

// Status 200 OK

{

"articles": [

    {

      "author_id": 888887,

      "draft": true,

      "id": 35467,

      "locale": "en",

      "permission_group_id": 123,

      "title": "Article title",

      "user_segment_id": 12

    }

]

}
```

### Show Article

- `GET /api/v2/help_center/articles/{article_id}`

Shows the properties of an article.

#### Allowed for

- Agents

#### Sideloads

The following sideloads are supported:

| Name         | Will sideload                                          |
| ------------ | ------------------------------------------------------ |
| users        | the author                                             |
| sections     | the section                                            |
| categories   | the category                                           |
| translations | the article, section and category translations, if any |

Unlike other sideloads, translations are embedded within the article because they're
not shared between resources.
Section and category translations are only sideloaded if present.

#### Parameters

| Name       | Type    | In   | Required | Description                  |
| ---------- | ------- | ---- | -------- | ---------------------------- |
| article_id | integer | Path | true     | The unique ID of the article |

#### Code Samples

**Python**

```python

import requests

from requests.auth import HTTPBasicAuth

url = "https://support.zendesk.com/api/v2/help_center/articles/360026053753"

headers = {

    "Content-Type": "application/json",

}

email_address = 'your_email_address'

api_token = 'your_api_token'

# Use basic authentication

auth = HTTPBasicAuth(f'{email_address}/token', api_token)

response = requests.request(

    "GET",

    url,

    auth=auth,

    headers=headers

)

print(response.text)
```

#### Example response(s)

**200 OK**

```json

// Status 200 OK

{

"article": {

    "author_id": 3465,

    "comments_disabled": true,

    "content_tag_ids": [

      "01GT23D51Y",

      "01GT23FWWN"

    ],

    "id": 37486578,

    "locale": "en_us",

    "permission_group_id": 123,

    "position": 42,

    "promoted": false,

    "title": "Article title",

    "user_segment_id": 12

}

}
```

### Show Article by Locale

- `GET /api/v2/help_center/{locale}/articles/{article_id}`

Shows the properties of an article.

**Note**: `{/locale}` is an optional parameter for admins and agents. End users and anonymous users must provide the parameter.

#### Allowed for

- Anonymous users

#### Sideloads

The following sideloads are supported:

| Name         | Will sideload                                          |
| ------------ | ------------------------------------------------------ |
| users        | the author                                             |
| sections     | the section                                            |
| categories   | the category                                           |
| translations | the article, section and category translations, if any |

Unlike other sideloads, translations are embedded within the article because they're
not shared between resources.
Section and category translations are only sideloaded if present.

#### Parameters

| Name       | Type    | In   | Required | Description                         |
| ---------- | ------- | ---- | -------- | ----------------------------------- |
| article_id | integer | Path | true     | The unique ID of the article        |
| locale     | string  | Path | true     | The locale the item is displayed in |

#### Code Samples

**Python**

```python

import requests

from requests.auth import HTTPBasicAuth

url = "https://support.zendesk.com/api/v2/help_center/en-us/articles/360026053753"

headers = {

    "Content-Type": "application/json",

}

email_address = 'your_email_address'

api_token = 'your_api_token'

# Use basic authentication

auth = HTTPBasicAuth(f'{email_address}/token', api_token)

response = requests.request(

    "GET",

    url,

    auth=auth,

    headers=headers

)

print(response.text)
```

#### Example response(s)

**200 OK**

```json

// Status 200 OK

{

"article": {

    "author_id": 3465,

    "comments_disabled": true,

    "content_tag_ids": [

      "01GT23D51Y",

      "01GT23FWWN"

    ],

    "id": 37486578,

    "locale": "en_us",

    "permission_group_id": 123,

    "position": 42,

    "promoted": false,

    "title": "Article title",

    "user_segment_id": 12

}

}
```

### Create Article in Section

- `POST /api/v2/help_center/sections/{section_id}/articles`

Creates an article in the specified [section](/api-reference/help_center/help-center-api/sections). You must specify an article title and locale. Optionally, specify a [user_segment_id](/api-reference/help_center/help-center-api/user_segments/#list-user-segments) (omit for a public article) and/or a [permission_group_id](/api-reference/help_center/help-center-api/permission_groups/#list-permission-groups) (omit to default to the Admins permission group). A locale must be specified for the article, either as a parameter in the API request or in the URL. The specified locales must be enabled for the current Help Center. Optionally, you can attach existing [content tags](/api-reference/help_center/help-center-api/content_tags) by their ids or specify multiple [translations](/api-reference/help_center/help-center-api/translations).

The current user is automatically subscribed to the article and
will receive notifications when it changes.

If a `permission_group_id` is specified, the current user must be a member of that permission group. To create a published article (`draft=false` or missing), the current user must have publishing rights as part of the permission group. Otherwise, the article must be created using `draft=true`.

Supplying a `notify_subscribers` property with a value of false will prevent subscribers to the article from receiving an article creation email notification. This can be helpful when creating many articles at a time. Specify the property in the root of the JSON object, not in the "article" object.

#### Allowed for

- Agents

#### Parameters

| Name       | Type    | In   | Required | Description                  |
| ---------- | ------- | ---- | -------- | ---------------------------- |
| section_id | integer | Path | true     | The unique ID of the section |

#### Example body

{

"article": {

    "body": "Use a tripod",

    "locale": "en-us",

    "permission_group_id": 56,

    "title": "Taking photos in low light",

    "user_segment_id": 123

},

"notify_subscribers": false

}

#### Code Samples

**Python**

```python

import requests

import json

from requests.auth import HTTPBasicAuth

url = "https://support.zendesk.com/api/v2/help_center/sections/360004785313/articles"

payload = json.loads("""{

"article": {

    "body": "Use a tripod",

    "locale": "en-us",

    "permission_group_id": 56,

    "title": "Taking photos in low light",

    "user_segment_id": 123

},

"notify_subscribers": false

}""")

headers = {

    "Content-Type": "application/json",

}

email_address = 'your_email_address'

api_token = 'your_api_token'

# Use basic authentication

auth = HTTPBasicAuth(f'{email_address}/token', api_token)

response = requests.request(

    "POST",

    url,

    auth=auth,

    headers=headers,

    json=payload

)

print(response.text)
```

#### Example response(s)

**201 Created**

```json

// Status 201 Created

{

"article": {

    "author_id": 3465,

    "comments_disabled": true,

    "content_tag_ids": [

      "01GT23D51Y",

      "01GT23FWWN"

    ],

    "id": 37486578,

    "locale": "en_us",

    "permission_group_id": 123,

    "position": 42,

    "promoted": false,

    "title": "Article title",

    "user_segment_id": 12

}

}
```

### Create Article

- `POST /api/v2/help_center/{locale}/sections/{section_id}/articles`

Creates an article in the specified [section](/api-reference/help_center/help-center-api/sections). You must specify an article title and locale. Optionally, specify a [user_segment_id](/api-reference/help_center/help-center-api/user_segments/#list-user-segments) (omit for a public article) and/or a [permission_group_id](/api-reference/help_center/help-center-api/permission_groups/#list-permission-groups) (omit to default to the Admins permission group). A locale must be specified for the article, either as a parameter in the API request or in the URL. The specified locales must be enabled for the current Help Center. Optionally, you can attach existing [content tags](/api-reference/help_center/help-center-api/content_tags) by their ids or specify multiple [translations](/api-reference/help_center/help-center-api/translations).

The current user is automatically subscribed to the article and
will receive notifications when it changes.

If a `permission_group_id` is specified, the current user must be a member of that permission group. To create a published article (`draft=false` or missing), the current user must have publishing rights as part of the permission group. Otherwise, the article must be created using `draft=true`.

Supplying a `notify_subscribers` property with a value of false will prevent subscribers to the article from receiving an article creation email notification. This can be helpful when creating many articles at a time. Specify the property in the root of the JSON object, not in the "article" object.

#### Allowed for

- Agents

#### Parameters

| Name       | Type    | In   | Required | Description                         |
| ---------- | ------- | ---- | -------- | ----------------------------------- |
| locale     | string  | Path | true     | The locale the item is displayed in |
| section_id | integer | Path | true     | The unique ID of the section        |

#### Example body

{

"article": {

    "body": "Use a tripod",

    "locale": "en-us",

    "permission_group_id": 56,

    "title": "Taking photos in low light",

    "user_segment_id": 123

},

"notify_subscribers": false

}

#### Code Samples

**Python**

```python

import requests

import json

from requests.auth import HTTPBasicAuth

url = "https://support.zendesk.com/api/v2/help_center/en-us/sections/360004785313/articles"

payload = json.loads("""{

"article": {

    "body": "Use a tripod",

    "locale": "en-us",

    "permission_group_id": 56,

    "title": "Taking photos in low light",

    "user_segment_id": 123

},

"notify_subscribers": false

}""")

headers = {

    "Content-Type": "application/json",

}

email_address = 'your_email_address'

api_token = 'your_api_token'

# Use basic authentication

auth = HTTPBasicAuth(f'{email_address}/token', api_token)

response = requests.request(

    "POST",

    url,

    auth=auth,

    headers=headers,

    json=payload

)

print(response.text)
```

#### Example response(s)

**201 Created**

```json

// Status 201 Created

{

"article": {

    "author_id": 3465,

    "comments_disabled": true,

    "content_tag_ids": [

      "01GT23D51Y",

      "01GT23FWWN"

    ],

    "id": 37486578,

    "locale": "en_us",

    "permission_group_id": 123,

    "position": 42,

    "promoted": false,

    "title": "Article title",

    "user_segment_id": 12

}

}
```

### Update Article

- `PUT /api/v2/help_center/articles/{article_id}`

These endpoints update article-level metadata such as its promotion status or
sorting position. The endpoints do not update translation properties such as
the article's title, body, locale, or draft. See [Translations](/api-reference/help_center/help-center-api/translations/).

#### Allowed for

- Agents

#### Parameters

| Name       | Type    | In   | Required | Description                  |
| ---------- | ------- | ---- | -------- | ---------------------------- |
| article_id | integer | Path | true     | The unique ID of the article |

#### Code Samples

**Python**

```python

import requests

from requests.auth import HTTPBasicAuth

url = "https://support.zendesk.com/api/v2/help_center/articles/360026053753"

headers = {

    "Content-Type": "application/json",

}

email_address = 'your_email_address'

api_token = 'your_api_token'

# Use basic authentication

auth = HTTPBasicAuth(f'{email_address}/token', api_token)

response = requests.request(

    "PUT",

    url,

    auth=auth,

    headers=headers

)

print(response.text)
```

#### Example response(s)

**200 OK**

```json

// Status 200 OK

{

"article": {

    "author_id": 3465,

    "comments_disabled": true,

    "content_tag_ids": [

      "01GT23D51Y",

      "01GT23FWWN"

    ],

    "id": 37486578,

    "locale": "en_us",

    "permission_group_id": 123,

    "position": 42,

    "promoted": false,

    "title": "Article title",

    "user_segment_id": 12

}

}
```

### Update Article by Locale

- `PUT /api/v2/help_center/{locale}/articles/{article_id}`

These endpoints update article-level metadata such as its promotion status or
sorting position. The endpoints do not update translation properties such as
the article's title, body, locale, or draft. See [Translations](/api-reference/help_center/help-center-api/translations/).

#### Allowed for

- Agents

#### Parameters

| Name       | Type    | In   | Required | Description                         |
| ---------- | ------- | ---- | -------- | ----------------------------------- |
| article_id | integer | Path | true     | The unique ID of the article        |
| locale     | string  | Path | true     | The locale the item is displayed in |

#### Code Samples

**Python**

```python

import requests

from requests.auth import HTTPBasicAuth

url = "https://support.zendesk.com/api/v2/help_center/en-us/articles/360026053753"

headers = {

    "Content-Type": "application/json",

}

email_address = 'your_email_address'

api_token = 'your_api_token'

# Use basic authentication

auth = HTTPBasicAuth(f'{email_address}/token', api_token)

response = requests.request(

    "PUT",

    url,

    auth=auth,

    headers=headers

)

print(response.text)
```

#### Example response(s)

**200 OK**

```json

// Status 200 OK

{

"article": {

    "author_id": 3465,

    "comments_disabled": true,

    "content_tag_ids": [

      "01GT23D51Y",

      "01GT23FWWN"

    ],

    "id": 37486578,

    "locale": "en_us",

    "permission_group_id": 123,

    "position": 42,

    "promoted": false,

    "title": "Article title",

    "user_segment_id": 12

}

}
```

### Update Article Source Locale

- `PUT /api/v2/help_center/articles/{article_id}/source_locale`

Updates the article's `source_locale` property. The source locale is the main language of the article. When you delete the article in the source locale, you delete all the article's translations.

The endpoint sets one of the article's translation as the source locale of the article. The article in the previous source locale becomes a translation, which you can delete separately.

The new source locale must be enabled in Guide. See [Enabling languages for your help center](https://support.zendesk.com/hc/en-us/articles/4408827609882#topic_ys2_kxh_tz). You can use the [List all enabled locales and default locale](/api-reference/help_center/help-center-api/translations/#list-enabled-locales-and-default-locale) endpoint to check for the enabled locales.

#### Allowed for

- Agents

#### Parameters

| Name       | Type    | In   | Required | Description                  |
| ---------- | ------- | ---- | -------- | ---------------------------- |
| article_id | integer | Path | true     | The unique ID of the article |

#### Code Samples

**Python**

```python

import requests

from requests.auth import HTTPBasicAuth

url = "https://support.zendesk.com/api/v2/help_center/articles/360026053753/source_locale"

headers = {

    "Content-Type": "application/json",

}

email_address = 'your_email_address'

api_token = 'your_api_token'

# Use basic authentication

auth = HTTPBasicAuth(f'{email_address}/token', api_token)

response = requests.request(

    "PUT",

    url,

    auth=auth,

    headers=headers

)

print(response.text)
```

#### Example response(s)

**200 OK**

```json

// Status 200 OK

null
```

### Update Article Source Locale by Locale

- `PUT /api/v2/help_center/{locale}/articles/{article_id}/source_locale`

Updates the article's `source_locale` property. The source locale is the main language of the article. When you delete the article in the source locale, you delete all the article's translations.

The endpoint sets one of the article's translation as the source locale of the article. The article in the previous source locale becomes a translation, which you can delete separately.

The new source locale must be enabled in Guide. See [Enabling languages for your help center](https://support.zendesk.com/hc/en-us/articles/224857687#topic_ys2_kxh_tz). You can use the [List all enabled locales and default locale](/api-reference/help_center/help-center-api/translations/#list-enabled-locales-and-default-locale) endpoint to check for the enabled locales.

#### Allowed for

- Agents

#### Parameters

| Name       | Type    | In   | Required | Description                         |
| ---------- | ------- | ---- | -------- | ----------------------------------- |
| article_id | integer | Path | true     | The unique ID of the article        |
| locale     | string  | Path | true     | The locale the item is displayed in |

#### Code Samples

**Python**

```python

import requests

from requests.auth import HTTPBasicAuth

url = "https://support.zendesk.com/api/v2/help_center/en-us/articles/360026053753/source_locale"

headers = {

    "Content-Type": "application/json",

}

email_address = 'your_email_address'

api_token = 'your_api_token'

# Use basic authentication

auth = HTTPBasicAuth(f'{email_address}/token', api_token)

response = requests.request(

    "PUT",

    url,

    auth=auth,

    headers=headers

)

print(response.text)
```

#### Example response(s)

**200 OK**

```json

// Status 200 OK

null
```

### Associate Attachments in Bulk to Article

- `POST /api/v2/help_center/articles/{article_id}/bulk_attachments`

You can associate attachments in bulk to only one article at a time,
with a maximum of 20 attachments per request.

To create the attachments, see [Create Unassociated Attachment](/api-reference/help_center/help-center-api/article_attachments#create-unassociated-attachment).

#### Allowed for

- Agents

#### Parameters

| Name       | Type    | In   | Required | Description                  |
| ---------- | ------- | ---- | -------- | ---------------------------- |
| article_id | integer | Path | true     | The unique ID of the article |

#### Code Samples

**Python**

```python

import requests

from requests.auth import HTTPBasicAuth

url = "https://support.zendesk.com/api/v2/help_center/articles/360026053753/bulk_attachments"

headers = {

    "Content-Type": "application/json",

}

email_address = 'your_email_address'

api_token = 'your_api_token'

# Use basic authentication

auth = HTTPBasicAuth(f'{email_address}/token', api_token)

response = requests.request(

    "POST",

    url,

    auth=auth,

    headers=headers

)

print(response.text)
```

#### Example response(s)

**200 OK**

```json

// Status 200 OK

null
```

### Associate Attachments in Bulk to Article by Locale

- `POST /api/v2/help_center/{locale}/articles/{article_id}/bulk_attachments`

You can associate attachments in bulk to only one article at a time,
with a maximum of 20 attachments per request.

To create the attachments, see [Create Unassociated Attachment](/api-reference/help_center/help-center-api/article_attachments#create-unassociated-attachment).

#### Allowed for

- Agents

#### Parameters

| Name       | Type    | In   | Required | Description                         |
| ---------- | ------- | ---- | -------- | ----------------------------------- |
| article_id | integer | Path | true     | The unique ID of the article        |
| locale     | string  | Path | true     | The locale the item is displayed in |

#### Code Samples

**Python**

```python

import requests

from requests.auth import HTTPBasicAuth

url = "https://support.zendesk.com/api/v2/help_center/en-us/articles/360026053753/bulk_attachments"

headers = {

    "Content-Type": "application/json",

}

email_address = 'your_email_address'

api_token = 'your_api_token'

# Use basic authentication

auth = HTTPBasicAuth(f'{email_address}/token', api_token)

response = requests.request(

    "POST",

    url,

    auth=auth,

    headers=headers

)

print(response.text)
```

#### Example response(s)

**200 OK**

```json

// Status 200 OK

null
```

### Archive Article by Locale

- `DELETE /api/v2/help_center/{locale}/articles/{article_id}`

Archives the article. You can restore the article using the Help Center user interface. See [Viewing and restoring archived articles](https://support.zendesk.com/hc/en-us/articles/4408822193434).

#### Allowed for

- Agents

#### Parameters

| Name       | Type    | In   | Required | Description                         |
| ---------- | ------- | ---- | -------- | ----------------------------------- |
| article_id | integer | Path | true     | The unique ID of the article        |
| locale     | string  | Path | true     | The locale the item is displayed in |

#### Code Samples

**Python**

```python

import requests

from requests.auth import HTTPBasicAuth

url = "https://support.zendesk.com/api/v2/help_center/en-us/articles/360026053753"

headers = {

    "Content-Type": "application/json",

}

email_address = 'your_email_address'

api_token = 'your_api_token'

# Use basic authentication

auth = HTTPBasicAuth(f'{email_address}/token', api_token)

response = requests.request(

    "DELETE",

    url,

    auth=auth,

    headers=headers

)

print(response.text)
```

#### Example response(s)

**204 No Content**

// Status 204 No Content

null

### List Articles in Category by Locale

- `GET /api/v2/help_center/{locale}/categories/{category_id}/articles`

These endpoints let you list all articles in Help Center, all articles in a given
category or section, or all the articles authored by a specific agent. You can
also list all articles with metadata that changed since a specified [start time](#start-time).

`{/locale}` is required only for end users or anonymous users. Admins and agents can omit it.

You can also use the Search API to list articles. See [Search](/api-reference/help_center/help-center-api/search).

#### Allowed for

- Agents
- End users
- Anonymous users

The response lists only the articles that the requesting agent,
end user, or anonymous user can view in Help Center.

#### Pagination

- Cursor pagination (recommended)
- Offset pagination

See [Pagination](/api-reference/introduction/pagination/).

#### Sorting

You can sort the results with the `sort_by` and `sort_order` query string parameters.

GET /api/v2/help_center/en-us/articles.json?sort_by=updated_at&sort_order=asc

The `sort_by` parameter can have one of the following values:

| value        | description                                                      |
| ------------ | ---------------------------------------------------------------- |
| `position`   | order set manually using the Arrange Content page. Default order |
| `title`      | order alphabetically by title                                    |
| `created_at` | order by creation time                                           |
| `updated_at` | order by update time                                             |
| `edited_at`  | order by the last time the title or body was edited              |

When sorting by `title`, the endpoint must specify a locale for the titles. Example:

/api/v2/help_center/en-us/articles.json?sort_by=title

Sorting by `edited_at` also requires a locale. The value specifies the locale in which the title or body was last changed.

The `sort_order` parameter can have one of the following values:

| value  | description      |
| ------ | ---------------- |
| `asc`  | ascending order  |
| `desc` | descending order |

Note that if sorting parameters are not passed to the section-scoped articles endpoint (`/api/v2/help_center/{locale}/sections/{section_id}/articles.json`), articles will be returned in the order defined on the section itself. See [Organizing knowledge base content in categories and sections](https://support.zendesk.com/hc/en-us/articles/4408845897370-Organizing-knowledge-base-content-in-categories-and-sections#topic_m3v_gq4_kk) for more information about defining sort orders on sections.

#### Options

##### Start Time

You can use the incremental article endpoint to list all the articles that were
updated since a certain date and time. The endpoint takes a `start_time` parameter
with a [Unix epoch time](http://www.epochconverter.com/). Example:

/api/v2/help_center/incremental/articles.json?start_time=1404345231

##### Label Names

You can specify that only articles with specific labels should be returned by adding
a `label_names` parameter. The parameter takes a comma-separated list of up to 10 label
names. Example:

/api/v2/help_center/en-us/articles.json?label_names=photos,camera

Only articles that have all the labels are returned. For example, `label_names=photos,camera` returns all articles that have both 'photo' AND 'camera' labels. If you want the articles that have either 'photo' OR 'camera' labels, you can use the [Search Article](/api-reference/help_center/help-center-api/search/#search-articles) endpoint with the `label_names` parameter (Professional and Enterprise).

Matching is case-sensitive. For example, 'camera' matches 'camera' but not 'Camera'.

#### Sideloads

The following sideloads are supported:

| Name         | Will sideload                                          |
| ------------ | ------------------------------------------------------ |
| users        | the author                                             |
| sections     | the section                                            |
| categories   | the category                                           |
| translations | the article, section and category translations, if any |

Unlike other sideloads, translations are embedded within the article because they're
not shared between resources.
Section and category translations are only sideloaded if present.

#### Parameters

| Name        | Type    | In    | Required | Description                                                                                                              |
| ----------- | ------- | ----- | -------- | ------------------------------------------------------------------------------------------------------------------------ |
| label_names | string  | Query | false    | Only articles that have all the labels are returned.                                                                     |
| sort_by     | string  | Query | false    | Sorts the articles by one of the accepted values. Allowed values are "position", "title", "created_at", or "updated_at". |
| sort_order  | string  | Query | false    | Selects the order of the results. Allowed values are "asc", or "desc".                                                   |
| start_time  | integer | Query | false    | You can use the incremental article endpoint to list all the articles that were updated since a certain date and time.   |
| category_id | integer | Path  | true     | The unique ID of the category                                                                                            |
| locale      | string  | Path  | true     | The locale the item is displayed in                                                                                      |

#### Code Samples

**Python**

```python

import requests

from requests.auth import HTTPBasicAuth

url = "https://support.zendesk.com/api/v2/help_center/en-us/categories/360002011513/articles?label_names=photos%2Ccamera&sort_by=&sort_order=&start_time=1404345231"

headers = {

    "Content-Type": "application/json",

}

email_address = 'your_email_address'

api_token = 'your_api_token'

# Use basic authentication

auth = HTTPBasicAuth(f'{email_address}/token', api_token)

response = requests.request(

    "GET",

    url,

    auth=auth,

    headers=headers

)

print(response.text)
```

#### Example response(s)

**200 OK**

```json

// Status 200 OK

{

"articles": [

    {

      "author_id": 888887,

      "draft": true,

      "id": 35467,

      "locale": "en",

      "permission_group_id": 123,

      "title": "Article title",

      "user_segment_id": 12

    }

]

}
```

### List Articles in Section by Locale

- `GET /api/v2/help_center/{locale}/sections/{section_id}/articles`

These endpoints let you list all articles in Help Center, all articles in a given
category or section, or all the articles authored by a specific agent. You can
also list all articles with metadata that changed since a specified [start time](#start-time).

`{/locale}` is required only for end users or anonymous users. Admins and agents can omit it.

You can also use the Search API to list articles. See [Search](/api-reference/help_center/help-center-api/search).

#### Allowed for

- Agents
- End users
- Anonymous users

The response lists only the articles that the requesting agent,
end user, or anonymous user can view in Help Center.

#### Pagination

- Cursor pagination (recommended)
- Offset pagination

See [Pagination](/api-reference/introduction/pagination/).

#### Sorting

You can sort the results with the `sort_by` and `sort_order` query string parameters.

GET /api/v2/help_center/en-us/articles.json?sort_by=updated_at&sort_order=asc

The `sort_by` parameter can have one of the following values:

| value        | description                                                      |
| ------------ | ---------------------------------------------------------------- |
| `position`   | order set manually using the Arrange Content page. Default order |
| `title`      | order alphabetically by title                                    |
| `created_at` | order by creation time                                           |
| `updated_at` | order by update time                                             |
| `edited_at`  | order by the last time the title or body was edited              |

When sorting by `title`, the endpoint must specify a locale for the titles. Example:

/api/v2/help_center/en-us/articles.json?sort_by=title

Sorting by `edited_at` also requires a locale. The value specifies the locale in which the title or body was last changed.

The `sort_order` parameter can have one of the following values:

| value  | description      |
| ------ | ---------------- |
| `asc`  | ascending order  |
| `desc` | descending order |

Note that if sorting parameters are not passed to the section-scoped articles endpoint (`/api/v2/help_center/{locale}/sections/{section_id}/articles.json`), articles will be returned in the order defined on the section itself. See [Organizing knowledge base content in categories and sections](https://support.zendesk.com/hc/en-us/articles/4408845897370-Organizing-knowledge-base-content-in-categories-and-sections#topic_m3v_gq4_kk) for more information about defining sort orders on sections.

#### Options

##### Start Time

You can use the incremental article endpoint to list all the articles that were
updated since a certain date and time. The endpoint takes a `start_time` parameter
with a [Unix epoch time](http://www.epochconverter.com/). Example:

/api/v2/help_center/incremental/articles.json?start_time=1404345231

##### Label Names

You can specify that only articles with specific labels should be returned by adding
a `label_names` parameter. The parameter takes a comma-separated list of up to 10 label
names. Example:

/api/v2/help_center/en-us/articles.json?label_names=photos,camera

Only articles that have all the labels are returned. For example, `label_names=photos,camera` returns all articles that have both 'photo' AND 'camera' labels. If you want the articles that have either 'photo' OR 'camera' labels, you can use the [Search Article](/api-reference/help_center/help-center-api/search/#search-articles) endpoint with the `label_names` parameter (Professional and Enterprise).

Matching is case-sensitive. For example, 'camera' matches 'camera' but not 'Camera'.

#### Sideloads

The following sideloads are supported:

| Name         | Will sideload                                          |
| ------------ | ------------------------------------------------------ |
| users        | the author                                             |
| sections     | the section                                            |
| categories   | the category                                           |
| translations | the article, section and category translations, if any |

Unlike other sideloads, translations are embedded within the article because they're
not shared between resources.
Section and category translations are only sideloaded if present.

#### Parameters

| Name        | Type    | In    | Required | Description                                                                                                              |
| ----------- | ------- | ----- | -------- | ------------------------------------------------------------------------------------------------------------------------ |
| label_names | string  | Query | false    | Only articles that have all the labels are returned.                                                                     |
| sort_by     | string  | Query | false    | Sorts the articles by one of the accepted values. Allowed values are "position", "title", "created_at", or "updated_at". |
| sort_order  | string  | Query | false    | Selects the order of the results. Allowed values are "asc", or "desc".                                                   |
| start_time  | integer | Query | false    | You can use the incremental article endpoint to list all the articles that were updated since a certain date and time.   |
| locale      | string  | Path  | true     | The locale the item is displayed in                                                                                      |
| section_id  | integer | Path  | true     | The unique ID of the section                                                                                             |

#### Code Samples

**Python**

```python

import requests

from requests.auth import HTTPBasicAuth

url = "https://support.zendesk.com/api/v2/help_center/en-us/sections/360004785313/articles?label_names=photos%2Ccamera&sort_by=&sort_order=&start_time=1404345231"

headers = {

    "Content-Type": "application/json",

}

email_address = 'your_email_address'

api_token = 'your_api_token'

# Use basic authentication

auth = HTTPBasicAuth(f'{email_address}/token', api_token)

response = requests.request(

    "GET",

    url,

    auth=auth,

    headers=headers

)

print(response.text)
```

#### Example response(s)

**200 OK**

```json

// Status 200 OK

{

"articles": [

    {

      "author_id": 888887,

      "draft": true,

      "id": 35467,

      "locale": "en",

      "permission_group_id": 123,

      "title": "Article title",

      "user_segment_id": 12

    }

]

}


```
