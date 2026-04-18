package au.mainspring.nativeapp.api

/** Join API root (with or without trailing slash) and a path starting with `/`. */
fun absolutizeApiUrl(baseUrl: String, pathOrUrl: String): String {
    if (pathOrUrl.startsWith("http://") || pathOrUrl.startsWith("https://")) {
        return pathOrUrl
    }
    return baseUrl.trimEnd('/') + "/" + pathOrUrl.trimStart('/')
}
