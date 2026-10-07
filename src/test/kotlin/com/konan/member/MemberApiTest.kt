package com.konan.member

import org.junit.jupiter.api.Test
import org.springframework.beans.factory.annotation.Autowired
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc
import org.springframework.boot.test.context.SpringBootTest
import org.springframework.http.MediaType
import org.springframework.test.web.servlet.MockMvc
import org.springframework.test.web.servlet.delete
import org.springframework.test.web.servlet.get
import org.springframework.test.web.servlet.post
import org.springframework.test.web.servlet.put

@SpringBootTest
@AutoConfigureMockMvc
class MemberApiTest(@Autowired private val mockMvc: MockMvc) {

    private fun json(name: String, email: String) = """{"name":"$name","email":"$email"}"""

    @Test
    fun `member crud flow`() {
        val location = mockMvc.post("/api/members") {
            contentType = MediaType.APPLICATION_JSON
            content = json("홍길동", "crud@example.com")
        }.andExpect { status { isCreated() } }
            .andReturn().response.getHeader("Location")!!

        mockMvc.get(location).andExpect {
            status { isOk() }
            jsonPath("$.name") { value("홍길동") }
        }

        mockMvc.put(location) {
            contentType = MediaType.APPLICATION_JSON
            content = json("김철수", "crud@example.com")
        }.andExpect { status { isOk() }; jsonPath("$.name") { value("김철수") } }

        mockMvc.get("/api/members").andExpect { status { isOk() } }

        mockMvc.delete(location).andExpect { status { isNoContent() } }
        mockMvc.get(location).andExpect { status { isNotFound() } }
    }

    @Test
    fun `duplicate email returns 409`() {
        repeat(2) { i ->
            mockMvc.post("/api/members") {
                contentType = MediaType.APPLICATION_JSON
                content = json("중복", "dup@example.com")
            }.andExpect { status { if (i == 0) isCreated() else isConflict() } }
        }
    }

    @Test
    fun `invalid input returns 400`() {
        mockMvc.post("/api/members") {
            contentType = MediaType.APPLICATION_JSON
            content = json("", "not-an-email")
        }.andExpect { status { isBadRequest() } }
    }
}
