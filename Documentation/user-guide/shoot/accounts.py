"""Screenshots of the Security pages and admin tools.

Every dialog is opened and then cancelled, so no user, role or permission is
changed. The user rows' icons are clicked by position (deactivate, password,
roles, delete), so check the order if the page changes: the last one deletes.
"""
from lib import *

with sync_playwright() as p:
    b, page = open_page(p, who="admin")
    goto(page, "/en/panel/users")

    def users():
        page.get_by_role("tab", name="User Management").click()
        time.sleep(3)
        shot(page, "sec_users")
        page.get_by_role("button", name="Add User").click()
        time.sleep(2)
        shot(page, "sec_add_user")
        close_dialog(page)
        actions = page.get_by_role("row").filter(has_text=MEMBER).first.locator("td").last.locator("button")
        assert actions.count() == 4, "expected 4 row icons, found %d" % actions.count()
        actions.nth(1).click()  # padlock: reset password
        time.sleep(2)
        shot(page, "sec_reset_password")
        close_dialog(page)
        actions.nth(2).click()  # badge: assign roles
        time.sleep(2)
        shot(page, "sec_assign_roles")
        close_dialog(page)
    safe(users)

    def roles():
        page.get_by_role("tab", name="Role Management").click()
        time.sleep(3)
        shot(page, "sec_roles", full=True)
        page.get_by_role("button", name="Create Role").click()
        time.sleep(2)
        shot(page, "sec_create_role")
        close_dialog(page)
        page.get_by_role("row").filter(has_text="Member").first.get_by_role("button", name="Manage").click()
        time.sleep(3)
        shot(page, "sec_role_permissions")
        close_dialog(page)
    safe(roles)

    def permissions():
        page.get_by_role("tab", name="Permissions").click()
        time.sleep(3)
        page.get_by_role("combobox").first.click()
        time.sleep(1)
        page.get_by_role("option").filter(has_text="Member").first.click()
        time.sleep(3)
        page.get_by_role("tab", name="TYPE PERMISSIONS").click()
        time.sleep(4)
        shot(page, "sec_perm_type", full=True)
        page.get_by_role("tab", name="Permission Checker").click()
        time.sleep(3)
        shot(page, "sec_checker")
        page.get_by_role("tab", name="Session Access").click()
        time.sleep(4)
        page.get_by_role("combobox").first.click()
        time.sleep(1)
        page.get_by_role("option").filter(has_text=LEGINON_SESSION).first.click()
        time.sleep(4)
        shot(page, "sec_session_access", full=True)
    safe(permissions)

    def admin_pages():
        goto(page, "/en/panel/plugins", wait=4)
        shot(page, "admin_plugins")
        goto(page, "/en/panel/admin/pipeline-health", wait=4)
        shot(page, "admin_health")
    safe(admin_pages)
    b.close()

    b, page = open_page(p)

    def own_password():
        goto(page, "/en/panel/users")
        page.get_by_role("button", name="Change Password").first.click()
        time.sleep(2)
        shot(page, "user_change_password")
        close_dialog(page)
    safe(own_password)
    b.close()
