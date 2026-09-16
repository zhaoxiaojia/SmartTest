from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
import json
from pathlib import Path
import re
from tempfile import NamedTemporaryFile

from core.product_lines import PRODUCT_LINE_BY_CONFLUENCE_LABEL

from .html import text
from .role_parser import extract_role_people


PAGE_ID = "607299166"
BUSINESS_PRODUCT_LINES = {
    label: line.name for label, line in PRODUCT_LINE_BY_CONFLUENCE_LABEL.items()
}
PRODUCT_LINE_ORDER = tuple(BUSINESS_PRODUCT_LINES.values())
UNCERTAIN_MARKERS = ("审批中", "offer申请中", "New", "Replace", "兼", "代")
BUSINESS_HEADERS = {"业务", "业务线", "业务方向", "业务归属", "产品线"}
PERSON_HEADER = re.compile(r"^(?:Owner|成员[1-8])$", re.I)


class PersonnelAssignmentAmbiguity(ValueError):
    def __init__(self, code):
        super().__init__(str(code))
        self.sync_stage = "invalid_table"
        self.sync_code = str(code)


class PersonnelAssignmentSync:
    """Own the Confluence-to-personnel assignment refresh transaction."""

    def __init__(
        self,
        gateway,
        personnel_path,
        *,
        key_resolver=None,
        jira_user_resolver=None,
        replace_file=None,
    ):
        self.gateway = gateway
        self.personnel_path = Path(personnel_path)
        self._key_resolver = key_resolver or getattr(gateway, "resolve_user_keys", None)
        self._jira_user_resolver = jira_user_resolver
        self._replace_file = replace_file or (lambda source, target: Path(source).replace(target))

    @staticmethod
    def _mark(error, stage, code):
        try:
            if not getattr(error, "sync_stage", ""):
                error.sync_stage = str(stage)
            if not getattr(error, "sync_code", ""):
                error.sync_code = str(code)
        except Exception:  # noqa: BLE001
            pass
        return error

    def refresh(self) -> bool:
        return self._refresh()

    def _refresh(self) -> bool:
        try:
            current = json.loads(self.personnel_path.read_text(encoding="utf-8"))
        except Exception as error:
            raise self._mark(error, "config_read", "personnel_config_read_failed")
        try:
            page = self.gateway.get_page(PAGE_ID)
        except Exception as error:
            raise self._mark(error, "confluence_rest", "confluence_rest_failed")
        body = str(page.body or "")
        try:
            assignments, additions, account_updates = self._extract(body, current)
        except PersonnelAssignmentAmbiguity:
            raise
        except Exception as error:
            raise self._mark(error, "person_parse", "person_parse_failed")
        try:
            updated = self._merge(current, assignments, additions, account_updates)
        except Exception as error:
            raise self._mark(error, "merge", "personnel_merge_failed")
        if updated == current:
            return False
        try:
            self._atomic_write(updated)
        except Exception as error:
            raise self._mark(error, "write", "personnel_atomic_write_failed")
        return True

    @staticmethod
    def _employees(personnel):
        departments = ((personnel.get("amlogic") or {}).get("departments") or {})
        return [
            employee
            for department in departments.values()
            for employee in (department.get("employees") or [])
            if isinstance(employee, dict)
        ]

    @staticmethod
    def _fae_qa_employees(personnel):
        department = (((personnel.get("amlogic") or {}).get("departments") or {}).get("FAE-QA") or {})
        return [employee for employee in (department.get("employees") or []) if isinstance(employee, dict)]

    @staticmethod
    def _tables(body):
        """Expand table rowspans while retaining the original cell body."""
        for table_html in re.findall(r"<table\b[^>]*>(.*?)</table>", body or "", re.I | re.S):
            active, rows = {}, []
            for row_index, row_html in enumerate(re.findall(r"<tr\b[^>]*>(.*?)</tr>", table_html, re.I | re.S)):
                raw_cells = re.findall(r"<t[hd]\b([^>]*)>(.*?)</t[hd]>", row_html, re.I | re.S)
                cells, column = [], 0
                for attributes, cell_html in raw_cells:
                    while column in active and active[column][0] >= row_index:
                        cells.append(active[column][1]); column += 1
                    row_match = re.search(r"\browspan\s*=\s*['\"]?(\d+)", attributes, re.I)
                    col_match = re.search(r"\bcolspan\s*=\s*['\"]?(\d+)", attributes, re.I)
                    rowspan = int(row_match.group(1)) if row_match else 1
                    colspan = int(col_match.group(1)) if col_match else 1
                    for _ in range(colspan):
                        while column in active and active[column][0] >= row_index:
                            cells.append(active[column][1]); column += 1
                        cells.append(cell_html)
                        if rowspan > 1:
                            active[column] = (row_index + rowspan - 1, cell_html)
                        column += 1
                while column in active and active[column][0] >= row_index:
                    cells.append(active[column][1]); column += 1
                active = {key: value for key, value in active.items() if value[0] > row_index}
                if cells:
                    rows.append(cells)
            if rows:
                yield rows

    def _extract(self, body, personnel):
        by_account = {
            str(employee.get("account") or "").strip().casefold(): employee
            for employee in self._fae_qa_employees(personnel)
            if str(employee.get("account") or "").strip()
        }
        blank_by_name = defaultdict(list)
        for employee in self._fae_qa_employees(personnel):
            if not str(employee.get("account") or "").strip():
                blank_by_name[str(employee.get("display_name") or "").strip().casefold()].append(employee)
        all_accounts = {
            str(employee.get("account") or "").strip().casefold()
            for employee in self._employees(personnel)
            if str(employee.get("account") or "").strip()
        }
        result, additions, account_updates = {}, {}, {}
        pending_keys, valid_table = [], False
        for table in self._tables(body):
            header_index = next((
                index for index, row in enumerate(table)
                if any(text(cell).strip() in BUSINESS_HEADERS for cell in row)
                and any(text(cell).strip().casefold() == "owner" for cell in row)
            ), None)
            if header_index is None:
                continue
            header = [text(cell).strip() for cell in table[header_index]]
            business_columns = [index for index, value in enumerate(header) if value in BUSINESS_HEADERS]
            person_columns = [index for index, value in enumerate(header) if PERSON_HEADER.fullmatch(value)]
            if len(business_columns) != 1 or not any(header[index].casefold() == "owner" for index in person_columns):
                continue
            valid_table = True
            business_index = business_columns[0]
            for cells in table[header_index + 1:]:
                if max([business_index, *person_columns]) >= len(cells):
                    raise PersonnelAssignmentAmbiguity("assignment_table_row_width_invalid")
                business = self._business_label(cells[business_index])
                if business is None:
                    continue
                product_line = BUSINESS_PRODUCT_LINES[business]
                for person_column in person_columns:
                    person_cell = cells[person_column]
                    person_text = text(person_cell).strip()
                    if not person_text and "<ri:user" not in person_cell.casefold():
                        continue
                    source = "ri-user" if "<ri:user" in person_cell.casefold() else "plain"
                    if any(marker.casefold() in person_text.casefold() for marker in UNCERTAIN_MARKERS):
                        continue
                    if source == "plain":
                        continue
                    people = extract_role_people(person_cell, business)
                    identities = [str(person.get("identity") or "").strip() for person in people]
                    for value in identities:
                        if not value:
                            continue
                        pending_keys.append((product_line, value))
        if not valid_table:
            raise PersonnelAssignmentAmbiguity("assignment_table_header_invalid")
        for pending, resolver, lookup_kind in ((pending_keys, self._key_resolver, "user_key"),):
            if not pending:
                continue
            names = tuple(dict.fromkeys(name for _line, name in pending))
            try:
                resolved = resolver(names) if resolver is not None else {}
            except Exception as error:
                raise self._mark(error, "confluence_rest", f"confluence_{lookup_kind}_lookup_failed")
            for product_line, name in pending:
                identity = resolved.get(name) if isinstance(resolved, dict) else None
                account = str((identity or {}).get("account") or "").strip().casefold()
                if account in by_account:
                    display_name = str(by_account[account].get("display_name") or "").strip()
                    result.setdefault(account, set()).add(product_line)
                else:
                    display_name = str((identity or {}).get("display_name") or "").strip()
                    blank_matches = blank_by_name.get(display_name.casefold(), []) if display_name else []
                    if account and len(blank_matches) == 1:
                        account_updates[display_name.casefold()] = str((identity or {}).get("account") or "").strip()
                        result.setdefault(account, set()).add(product_line)
                        continue
                    verified = self._verify_jira_identity(account, display_name)
                    if verified is not None and account not in all_accounts:
                        additions.setdefault(account, verified)
                        result.setdefault(account, set()).add(product_line)
        if not result:
            raise PersonnelAssignmentAmbiguity("assignment_table_no_fae_qa_match")
        return result, additions, account_updates

    def _verify_jira_identity(self, account, display_name):
        if not account or not display_name or self._jira_user_resolver is None:
            return None
        try:
            candidates = self._jira_user_resolver(account) or ()
        except Exception:  # one unverified identity must not block other explicit people
            return None
        matches = [
            candidate for candidate in candidates
            if isinstance(candidate, dict)
            and str(candidate.get("account") or "").strip().casefold() == account
            and str(candidate.get("display_name") or "").strip().casefold() == display_name.casefold()
            and candidate.get("active") is True
        ]
        if len(matches) != 1:
            return None
        return {
            "display_name": display_name,
            "account": account,
            "reports_to": "",
            "active": True,
            "organization": {"team": "", "division": ""},
            "employment": {"grade": "", "job_title_override": "", "employee_type": ""},
            "assignments": [],
            "expertise_domains": [],
            "system_roles": ["user"],
        }

    @staticmethod
    def _business_label(cell_html):
        source = str(cell_html or "")
        for label in BUSINESS_PRODUCT_LINES:
            if re.match(
                rf"^\s*(?:<[^>]+>\s*)*{re.escape(label)}(?=$|\s|<|&)",
                source,
            ):
                return label
        return None

    def _merge(self, current, explicit, additions=(), account_updates=()):
        updated = deepcopy(current)
        qa_department = (((updated.get("amlogic") or {}).get("departments") or {}).get("FAE-QA") or {})
        qa_employees = qa_department.get("employees") or []
        for employee in qa_employees:
            display_name = str(employee.get("display_name") or "").strip().casefold()
            if not str(employee.get("account") or "").strip() and display_name in account_updates:
                employee["account"] = account_updates[display_name]
                if not employee.get("system_roles"):
                    employee["system_roles"] = ["user"]
        qa_employees.extend(deepcopy(list(additions.values())))
        qa_accounts = {str(employee.get("account") or "").strip().casefold()
                       for employee in self._fae_qa_employees(updated)}
        owner_lines = defaultdict(list)
        amlogic = updated.get("amlogic") or {}
        for catalog in (amlogic.get("product_lines") or (), amlogic.get("technical_centers") or ()):
            for item in catalog:
                if not isinstance(item, dict):
                    continue
                owner = str(item.get("owner_account") or "").strip().casefold()
                line = str(item.get("id") or "").strip()
                if owner and line and line not in owner_lines[owner]:
                    owner_lines[owner].append(line)
        for employee in self._employees(updated):
            account = str(employee.get("account") or "").strip()
            normalized = account.casefold()
            page_lines = explicit.get(account, explicit.get(normalized, set())) if normalized in qa_accounts else set()
            target_lines = [line for line in PRODUCT_LINE_ORDER if line in page_lines]
            target_lines.extend(line for line in owner_lines.get(normalized, ()) if line not in target_lines)
            if target_lines or employee.get("assignments"):
                existing = {
                    str(item.get("product_line_id") or ""): item
                    for item in (employee.get("assignments") or [])
                    if isinstance(item, dict)
                }
                employee["assignments"] = [
                    {
                        "product_line_id": product_line,
                        "responsibilities": [],
                        **{key: value for key, value in existing.get(product_line, {}).items()
                           if key not in {"product_line_id", "primary"}},
                    }
                    for product_line in target_lines
                ]
        return updated

    def _atomic_write(self, value):
        temporary = None
        try:
            with NamedTemporaryFile(
                "w", encoding="utf-8", dir=self.personnel_path.parent,
                prefix=f".{self.personnel_path.name}.", suffix=".tmp", delete=False,
            ) as stream:
                json.dump(value, stream, ensure_ascii=False, indent=2)
                stream.write("\n")
                temporary = Path(stream.name)
            self._replace_file(temporary, self.personnel_path)
        finally:
            if temporary is not None and temporary.exists():
                temporary.unlink()
