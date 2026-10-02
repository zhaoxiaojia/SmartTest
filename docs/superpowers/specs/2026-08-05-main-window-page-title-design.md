# Main Window Page Title Design

## Goal

Remove the large page-title header from every page hosted by the main navigation window, except that Home already has no such label. Show the active page identity in the application title bar instead:

- Home: `SmartTest`
- Test: `SmartTest.Test`
- Tool: `SmartTest.Tool`
- Other main-navigation pages: `SmartTest.<navigation title>`

Business headings inside page content, such as `Schedule`, `redmine`, `Issues`, dialogs, cards, and section titles, remain unchanged.

## Scope

This behavior applies only to pages hosted by `MainWindow.qml` through its primary `FluNavigationView`. Standalone windows, dialogs, page windows, and other consumers of `FluPage` keep their current title headers unless they explicitly opt out.

## Design

### FluentUI page capability

Add an opt-out property to `FluPage` that controls whether its standard title header is created. Its default remains enabled to preserve existing FluentUI and standalone-window behavior.

### Navigation ownership

Add a main-navigation setting to `FluNavigationView` that suppresses the standard header on pages it creates. The setting is applied consistently to newly created pages and cached `SingleInstance` pages. It must not clear the page's `title` property, because that title remains useful as page identity.

The navigation view exposes the currently selected navigation title as read-only presentation state. It derives this from the selected navigation model item rather than parsing a URL or inspecting page content.

### Main-window title

`MainWindow.qml` enables page-header suppression for its navigation view and builds one display title from the selected navigation title:

- If the selected page is Home, display `SmartTest`.
- Otherwise display `SmartTest.` followed by the selected localized navigation title.

The same value drives both the operating-system window title and the visible FluentUI application-bar label, so they cannot drift apart.

Navigation by sidebar click, search, back, footer item, and cached-page restoration must all update the title through the navigation selection state.

## Localization

`SmartTest` remains the product name. Page names reuse the already localized navigation-item titles; no duplicate page-name translations are introduced. The dot is a fixed product-title separator.

## Validation

Runtime QML tests will verify:

1. A standalone `FluPage` still shows its title header by default.
2. The main navigation suppresses the page header without erasing page identity.
3. Home displays `SmartTest`.
4. Test, Tool, another primary page, a footer page, and back navigation display the matching `SmartTest.<page>` title.
5. QML loads without new warnings.

After rebuilding the relevant QRC files, source runtime validation will open the actual main window and visually confirm that the former large page-title strip is gone and the recovered vertical space belongs to page content. No packaged application build is included.
