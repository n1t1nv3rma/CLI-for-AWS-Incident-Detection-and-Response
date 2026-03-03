// This is an example Authentication Lambda that is configured for use with the Dynatrace APM, using a header named authorizationToken.
// Please edit this code accordingly to meet your internal security posture and/or APM requirements.
const crypto = require("crypto");
const {
    SecretsManagerClient,
    GetSecretValueCommand
} = require("@aws-sdk/client-secrets-manager");

exports.handler = async(event) => {

    const secret_name = process.env.EnvSecretName;
    const client = new SecretsManagerClient({
        region: process.env.AWS_REGION
    });

    let response;

    try {
        response = await client.send(
            new GetSecretValueCommand({
                SecretId: secret_name,
                VersionStage: "AWSCURRENT",
            })
        );
    } catch (error) {
        console.log("======= Authorization Failure: Secrets Manager error =======");
        return {
            "principalId": "idrAuth",
            "policyDocument": {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Action": "execute-api:Invoke",
                        "Resource": [event["methodArn"]],
                        "Effect": "Deny"
                    }
                ]
            }
        };
    }

    const secret = response.SecretString;

    const token = event['authorizationToken'];
    const resource = event["methodArn"];

    let permission = "Deny";
    let authResult;

    try {
        const expectedToken = JSON.parse(secret).APMSecureToken;
        if (expectedToken && token.length === expectedToken.length &&
            crypto.timingSafeEqual(Buffer.from(token), Buffer.from(expectedToken))) {
            permission = "Allow";
            authResult = "======= Authorization Success =======";
        } else {
            authResult = "======= Authorization Failure =======";
        }
    } catch (error) {
        authResult = "======= Authorization Failure: Unable to parse secret =======";
    }
    console.log(authResult);

    const authResponse = {
        "principalId": "idrAuth",
        "policyDocument": {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Action": "execute-api:Invoke",
                    "Resource": [resource],
                    "Effect": permission
                }
            ]
        }
    };
    return authResponse;
};