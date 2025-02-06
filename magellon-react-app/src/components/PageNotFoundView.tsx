// import * as animationData from '../../assets/lottie/coffee_time.json'
// import Lottie from "lottie-react";
const IMAGES2 = {
    image1 : new URL('../../assets/images/Error404.png', import.meta.url).href
}
export const PageNotFoundView = () => {
    // const defaultOptions = {
    //     loop: true,
    //     autoplay: true,
    //     animationData: animationData,
    //     rendererSettings: {
    //         preserveAspectRatio: 'xMidYMid slice'
    //     }
    // };

    return (
        <>
            <h1>Page not found</h1>
            <img src={IMAGES2.image1}/>
            {/*<Lottie animationData={animationData}                    loop={true}/>*/}
        </>
    );
};
