import os
import asyncio
import typing as T
import gitlab
import markdown
import re
import manager.master.configs as share
from bs4 import BeautifulSoup
from tabulate import tabulate
from manager.master.exceptions import CUSTOM_FUNC_DOC_GEN_FAIL, \
    DOC_GEN_FAILED_TO_GENERATE
from concurrent.futures import ThreadPoolExecutor


gitlab_url = "http://10.5.4.211:8011"


async def custom_init() -> None:
    return


async def doc_gen(
        contents: T.List[T.Tuple[str, T.List[str]]],
        path: str) -> T.Optional[str]:

    changelogfile = open(path, "w")

    for content in contents:
        ver, logs = content

        if len(logs) == 0:
            continue

        table = []
        table.append(["WTD_NO", "ISSUE", "DESCRIPTION"])

        for line in logs:
            # Fetch issue
            search = re.search("#[0-9]*", line)
            if search is None:
                # No issue id reside in this comment
                table.append(["N/A", "N/A", line])
                continue

            iid = search.group()[1:]

            with ThreadPoolExecutor() as e:
                issue = await asyncio.get_running_loop()\
                            .run_in_executor(e, issue_fetch, iid)

            try:
                table.append(
                    data_fetch(iid, issue)
                )
            except Exception:
                # Cleanup and raise an excepiton to notify
                # upper component.
                changelogfile.close()
                os.remove(path)

                raise DOC_GEN_FAILED_TO_GENERATE()

        changelogfile.write(ver+":\n"+tabulate(table)+"\n")

    return path


def issue_fetch(iid: str) -> T.Any:
    try:
        ref = gitlab.Gitlab(gitlab_url, "Am44wPpH4m1Uf_ykzSLA")
        ref.auth()

        proj = ref.projects.get(34)
        return proj.issues.get(iid)
    except Exception as e:
        raise CUSTOM_FUNC_DOC_GEN_FAIL(e)


def data_fetch(iid: str, issue: T.Any) -> T.List[str]:
    desc_html = markdown.markdown(issue.description)
    bs = BeautifulSoup(desc_html)

    # Find out WTD_NO
    wtd_no = wtd_no_extract(bs)

    # Find out WTD_Description
    wtd_description = wtd_description_extract(bs)
    if wtd_description == "N/A":
        wtd_description = issue.title

    return [wtd_no, iid, wtd_description]


def wtd_description_extract(bs: BeautifulSoup) -> str:
    headers = related_field_get(bs)

    if len(headers) != 1:
        return "N/A"

    desc_maybe = headers[0].findNextSibling().getText()
    desc_maybe = desc_maybe.strip()
    pos = desc_maybe.find("\n")

    if pos != -1:
        desc_maybe = desc_maybe[pos+1:]

    if re.match("wtd(-|.)*", desc_maybe) is None:
        return desc_maybe
    else:
        return "N/A"


def wtd_no_extract(bs: BeautifulSoup) -> str:
    wtd_no = wtd_no_extract_within_header("h1", bs)
    if wtd_no == "N/A":
        return wtd_no_extract_within_header("h2", bs)

    return wtd_no


def wtd_no_extract_within_header(header: str, bs) -> str:
    headers = related_field_get(bs)

    if len(headers) != 1:
        return "N/A"

    return headers[0].findNextSibling().find('a').getText()


def related_field_get(bs: BeautifulSoup) -> T.Any:
    headers = bs.find_all("h1") + bs.find_all("h2")
    return [
        s for s in headers if s.getText() == 'Related_SN:'
        or s.getText() == 'Related_SN'
    ]
