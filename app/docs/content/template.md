---
title: Template Documentation Article
description: An example of a documentation article.
group: Development
visibility: public
order: 0
topics: [development, templates, articles]
---

# Table of Contents
Below is an automatically generated table of contents for this article using `[TOC]`.

[TOC]

---


# Attributes
These articles have a number of possible YAML frontmatter attributes. Some of these are required, while others are optional.

- Title (required)
- Description
- Group (required)
- Visibility
- Order
- Topics

## More Information
While title and group are required, the rest are optional.  
The group attribute is used to organize the articles. It's not required to put them into a folder of the same name, but it can help (see the core group as a reference).
The group attribute should be a string (in title-case for consistency) and should not contain special characters or spaces.
Descriptions will remain empty if not provided, but are highly recommended.  
Visibility options are `public` or `private` and will default to `private` if not provided. Assuming the "Restrict Docs" setting is disabled, anyone can view public articles without signing in.  
Order is number that will default to `100` if not provided so that it will appear after other articles.  
Topics are a list of strings used to help categorize the article.

# Content
The content of the article is written in Markdown and can be as long as you want. The content will be rendered as HTML (which may result in a few issues with formatting).  
Once being rendered, the content is shown via Tailwind's `prose` class, which is a set of styles that make the content look nice without effort on the development side.

You can pass in jinja variables and functions to the content of the article by using the standard Jinja syntax.
The formatter is also aware of `doc_link_search(query)`, `doc_link_article(slug)`, and `image_link(path)` functions for rendering links to other articles. It's best to create these articles, copy their slug in the browser, and use them as a reference.  
For example:

- `doc_link_article("development/template-documentation-article")` will render a link to this article [(click here)]({{ doc_link_article("development/template-documentation-article") }})
- `doc_link_search("template")` will render a link to the search results for "template" [(click here)]({{ doc_link_search("template") }})
- `image_link("victor-g-N04FIfHhv_k-unsplash.jpg")` will render a link to an image that you can use in an image tag with `![alt text](image link function)`. These images must be placed in the `core/static/images/docs` directory.

![alt text]({{ image_link("victor-g-N04FIfHhv_k-unsplash.jpg") }})

## Other Features
This system supports several Python-Markdown extensions to enhance your documentation layout and formatting.

### Tables
Tables are a native way to organize complex configurations or structural data clearly inside an article:

| Attribute | Type | Default Value | Description |
| :--- | :--- | :--- | :--- |
| `visibility` | String | `private` | Defines who can access the documentation. |
| `order` | Integer | `100` | Controls the sorting weight in navigation lists. |
| `topics` | Array | `[]` | Keywords used to index and discover content. |

### Lists
The `sane_lists` extension ensures that switching your block item syntax transitions cleanly between ordered lists (`<ol>`) and unordered lists (`<ul>`) without layout bugs.  
Make sure to leave an empty or lists will not render properly!

- First unordered item categorizing tools
- Second unordered item categorizing workflows

1. First ordered step to publish an article
2. Second ordered step to verify visibility

### Code Fencing
You can use fenced code blocks to highlight code snippets.
```python
print("Hello, World!")
```