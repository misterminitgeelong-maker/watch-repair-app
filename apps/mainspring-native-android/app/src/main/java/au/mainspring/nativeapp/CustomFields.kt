package au.mainspring.nativeapp

import com.google.gson.JsonObject
import com.google.gson.JsonParser

/** Which job family a custom-field set belongs to (web `jobType`: repair_job, shoe_repair_job, auto_key_job). */
enum class CustomFieldJobKind { Watch, Shoe, Mobile }

/** Pure helpers shared by the view model and unit tests. */
object CustomFields {
    /** Parse `custom_fields_json`; anything unparseable or not an object is an empty set, like the web. Insertion order is kept. */
    fun parse(json: String?): LinkedHashMap<String, String> {
        val out = LinkedHashMap<String, String>()
        if(json.isNullOrBlank()) return out
        try {
            val el = JsonParser.parseString(json)
            if(!el.isJsonObject) return out
            for((k, v) in el.asJsonObject.entrySet()) out[k] = if(v.isJsonNull) "" else if(v.isJsonPrimitive) v.asString else v.toString()
        } catch(_: Exception) { out.clear() }
        return out
    }

    /** Read the `custom_fields_json` property from a raw job document. */
    fun fromJob(job: JsonObject): LinkedHashMap<String, String> {
        val raw = job.get("custom_fields_json")
        return if(raw == null || raw.isJsonNull) LinkedHashMap() else if(raw.isJsonPrimitive) parse(raw.asString) else parse(raw.toString())
    }

    /** Trimmed, non-blank name or null. Names are the map keys, so they are trimmed like the web's `newKey.trim()`. */
    fun cleanName(name: String): String? = name.trim().takeIf { it.isNotEmpty() }
}
