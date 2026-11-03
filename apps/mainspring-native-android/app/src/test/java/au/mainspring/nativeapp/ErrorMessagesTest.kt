package au.mainspring.nativeapp
import org.junit.*
import okhttp3.ResponseBody.Companion.toResponseBody
import retrofit2.HttpException
import retrofit2.Response
class ErrorMessagesTest {
 @Test fun displaysBackendValidationFieldInsteadOfOnlyHttpStatus() {
  val error = HttpException(Response.error<Any>(422, """{"detail":[{"loc":["body","key_quantity"],"msg":"Input should be greater than 0"}]}""".toResponseBody()))
  Assert.assertEquals("key_quantity: Input should be greater than 0", error.userMessage())
 }
 @Test fun doesNotShowProxyHtmlToUser() {
  val error = HttpException(Response.error<Any>(503, "<html><body>proxy error</body></html>".toResponseBody()))
  Assert.assertFalse(error.userMessage().contains("html")); Assert.assertTrue(error.userMessage().contains("503"))
 }
}
