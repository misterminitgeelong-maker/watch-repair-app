package au.mainspring.nativeapp.api

import okhttp3.ResponseBody
import retrofit2.HttpException
import retrofit2.Response

/** Gson cannot decode an empty 204 body; use [ResponseBody] and close the stream. */
fun Response<ResponseBody>.requireSuccessEmptyBody() {
    if (!isSuccessful) throw HttpException(this)
    body()?.close()
}
