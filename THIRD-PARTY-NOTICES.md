# Third-Party Notices

This package redistributes the `windtrader-java` validator as a shaded (uber) JAR. That JAR is
derived from the OMG SysML v2 Pilot Implementation (EPL-2.0) and may embed third-party components,
each governed by its own license and notices. EPL-2.0 §3.3 requires that these notices not be
removed or altered.

## Known embedded components

- **Eclipse Xtext / EMF** — Eclipse Public License 2.0 (EPL-2.0)
- **ANTLR** — BSD 3-Clause
- **Other Apache-2.0 / BSD dependencies of the pilot** — per their own notices

The authoritative list of notices is whatever ships inside the bundled JAR under
`META-INF/LICENSE*` and `META-INF/NOTICE*` (or equivalent). When a JAR is bundled, its embedded
license/notice files should be extracted into this file (or an accompanying file) so the notices
survive redistribution.

> Follow-up: `sync-from-java-release.yml` should extract `META-INF/LICENSE*`/`META-INF/NOTICE*`
> from the JAR at sync time and fail the build if the JAR's declared license is not EPL-2.0.
