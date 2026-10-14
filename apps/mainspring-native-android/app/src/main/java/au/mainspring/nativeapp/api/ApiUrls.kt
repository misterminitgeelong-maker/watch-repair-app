package au.mainspring.nativeapp.api

/** Join API root (with or without trailing slash) and a path starting with `/`. */
fun absolutizeApiUrl(baseUrl: String, pathOrUrl: String): String {
    if (pathOrUrl.startsWith("http://") || pathOrUrl.startsWith("https://")) {
        return pathOrUrl
    }
    return baseUrl.trimEnd('/') + "/" + pathOrUrl.trimStart('/')
}

/**
 * Customer approval page for a sent quote. The web app is served from the same origin as the API
 * (docs/DEPLOY.md), so the link is `<api origin>/approve/<token>`, matching the web "Copy approval link".
 */
fun quoteApprovalLink(apiBaseUrl: String, approvalToken: String): String {
    val uri = java.net.URI(apiBaseUrl.trim())
    val origin = if (uri.scheme != null && uri.host != null) "${uri.scheme}://${uri.host}" + (if (uri.port != -1) ":${uri.port}" else "") else apiBaseUrl.trimEnd('/')
    return "$origin/approve/$approvalToken"
}
