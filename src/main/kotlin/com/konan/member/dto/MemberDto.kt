package com.konan.member.dto

import com.konan.member.domain.Member
import jakarta.validation.constraints.Email
import jakarta.validation.constraints.NotBlank
import jakarta.validation.constraints.Size

data class MemberRequest(
    @field:NotBlank
    @field:Size(max = 50)
    val name: String,

    @field:NotBlank
    @field:Email
    @field:Size(max = 100)
    val email: String,
)

data class MemberResponse(
    val id: Long,
    val name: String,
    val email: String,
) {
    companion object {
        fun from(member: Member) = MemberResponse(
            id = requireNotNull(member.id),
            name = member.name,
            email = member.email,
        )
    }
}
