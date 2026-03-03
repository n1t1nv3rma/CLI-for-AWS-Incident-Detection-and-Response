// This is an example Authentication Lambda that is configured for use with the Self-Hosted Grafana APM, using the Authorization header.
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

    const authHeader = event.headers?.Authorization || event.headers?.authorization;
    const resource = event["methodArn"];
    let permission = "Deny";

    if (!authHeader || !authHeader.startsWith("Bearer ")) {
        console.log("======= Authorization Failure: Missing or invalid Bearer token =======");
        return buildPolicy(resource, permission);
    }

    const token = authHeader.split(" ")[1];

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
        return buildPolicy(resource, permission);
    }

    const secret = response.SecretString;

    try {
        const expectedToken = JSON.parse(secret).APMSecureToken;
        if (expectedToken && token.length === expectedToken.length &&
            crypto.timingSafeEqual(Buffer.from(token), Buffer.from(expectedToken))) {
            permission = "Allow";
            console.log("======= Authorization Success =======");
        } else {
            console.log("======= Authorization Failure =======");
        }
    } catch (error) {
        console.log("======= Authorization Failure: Unable to parse secret =======");
    }

    return buildPolicy(resource, permission);
};

function buildPolicy(resource, permission) {
    return {
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
}